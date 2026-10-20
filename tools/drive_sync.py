#!/usr/bin/env python3
"""Authenticated, read-only Drive -> local previews. Default: metadata inventory.
No Git push, PR, timer or deployment. Originals exist in memory only.
"""
import argparse
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import warnings

from PIL import Image, ImageCms, ImageOps
import sync_motifs as images

FOLDER = 'application/vnd.google-apps.folder'
SYNC_VERSION = 1
MAX_BYTES = 64 * 1024 * 1024
MAX_PIXELS = 40_000_000
MAX_REFERENCED_BYTES = 512 * 1024 * 1024
MAX_SITE_ASSET_BYTES = 800 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = MAX_PIXELS
FORMATS = {'image/png': 'PNG', 'image/jpeg': 'JPEG', 'image/webp': 'WEBP', 'image/gif': 'GIF'}
PUBLIC_FILES = {'catalog.json', 'data/categories.json', 'data/motifs-manifest.json', 'data/drive-sync-state.json'}
SECRET = re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|AIza[A-Za-z0-9_-]{30,}|ya29\.[A-Za-z0-9_.-]{20,}|1//[A-Za-z0-9_-]{30,}|AKIA[A-Z0-9]{16}|eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}')


class SyncError(Exception):
    pass


MAPPING_ERROR = ('Widerspruechliche oder mehrdeutige Erstzuordnung. Keine Aenderungen angewandt. '
                 'Ordnernamen und bisherige Motivzuordnung privat pruefen; eine bestaetigte '
                 'Zuordnung lokal mit --category-bindings angeben.')


class MappingError(SyncError):
    def __init__(self):
        super().__init__(MAPPING_ERROR)


def load_category_bindings(path, root):
    """Private, local-only input; never upload this file or use it in public CI."""
    if os.environ.get('GITHUB_ACTIONS') == 'true' or path.resolve().is_relative_to(root.resolve()):
        raise SyncError('Private mapping input must stay outside the repository and public CI.')
    data = images.read_json(path)
    if not isinstance(data, dict) or set(data) != {'version', 'bindings'} or data['version'] != 1 or not isinstance(data['bindings'], dict):
        raise MappingError()
    for category_id, folder_id in data['bindings'].items():
        images.valid_id(category_id)
        images.valid_id(folder_id)
    return data['bindings']


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise SyncError('Google API redirect refused; credentials were not forwarded.')


def public_text(value):
    def check_keys(data):
        if isinstance(data, dict):
            if any(str(key).casefold().replace('-', '_') in {'access_token', 'refresh_token', 'private_key', 'client_secret', 'credentials_json', 'authorization'} for key in data):
                raise SyncError('Credential field in generated data; publication refused.')
            for item in data.values():
                check_keys(item)
        elif isinstance(data, list):
            for item in data:
                check_keys(item)
    check_keys(value)
    if SECRET.search(json.dumps(value, ensure_ascii=False)):
        raise SyncError('Potential secret in generated data; publication refused.')


def public_manifest(manifest):
    if set(manifest) - {'version', 'generatedAt', 'generator', 'originalPolicy', 'motifs'}:
        raise SyncError('Unknown public manifest fields.')
    for entry in manifest['motifs']:
        if set(entry) - {'id', 'name', 'category', 'categoryId', 'source', 'sourceFingerprint', 'previewSource', 'variants', 'originalFingerprint', 'syncVersion', 'generator'}:
            raise SyncError('Unknown motif fields; no raw source data may be published.')
        images.valid_id(entry['id'])
        if not isinstance(entry['name'], str) or not entry['name'].strip():
            raise SyncError('Invalid motif label.')
        if set(entry['source']) - {'provider', 'fileId', 'originalUrl', 'originalFilename', 'rootFolderId', 'modifiedTime', 'md5Checksum', 'size', 'version', 'folderIds', 'folderNames', 'mimeType'}:
            raise SyncError('Unknown source metadata fields.')
        if set(entry['previewSource']) - {'kind', 'requestedWidth', 'requestedSize', 'sha256', 'bytes', 'mimeType', 'format', 'width', 'height'}:
            raise SyncError('Unknown preview-source fields.')
        if set(entry['variants']) != {'600', '1600'}:
            raise SyncError('Only the two public preview variants are permitted.')
        for meta in entry['variants'].values():
            if set(meta) != {'path', 'width', 'height', 'bytes', 'sha256', 'pixelSha256', 'losslessVerified'}:
                raise SyncError('Unknown variant metadata fields.')
    public_text(manifest)


def allowed_path(value):
    return value in PUBLIC_FILES or bool(re.fullmatch(r'assets/motifs/[A-Za-z0-9_-]+/(600|1600)-[a-f0-9]{16}\.webp', value))


class DriveAPI:
    def __init__(self, token, opener=None):
        if not token:
            raise SyncError('A short-lived WIF access token is required.')
        self.token = token
        self.opener = opener or urllib.request.build_opener(NoRedirect())
        self.requests = 0

    def get(self, path, params, maximum=2 * 1024 * 1024):
        if path != 'files' and not re.fullmatch(r'files/[A-Za-z0-9_-]+', path):
            raise SyncError('Unexpected Drive API path.')
        url = 'https://www.googleapis.com/drive/v3/' + path + '?' + urllib.parse.urlencode(params)
        for attempt in range(4):
            self.requests += 1
            if self.requests > 10000:
                raise SyncError('API request safety limit exceeded.')
            request = urllib.request.Request(url, method='GET', headers={'Authorization': 'Bearer ' + self.token, 'Accept': '*/*' if params.get('alt') == 'media' else 'application/json'})
            try:
                with self.opener.open(request, timeout=30) as response:
                    body = response.read(maximum + 1)
                if len(body) > maximum:
                    raise SyncError('Drive response exceeds the configured byte limit.')
                return body
            except urllib.error.HTTPError as error:
                code = error.code
                if code not in (429, 500, 502, 503, 504) or attempt == 3:
                    raise SyncError(f'Drive GET failed (HTTP {code}); no metadata update.') from None
            except (urllib.error.URLError, OSError):
                if attempt == 3:
                    raise SyncError('Drive network/TLS error; no metadata update.') from None
            time.sleep(2 ** attempt)
        raise SyncError('Drive request failed.')

    def json(self, path, params):
        try:
            data = json.loads(self.get(path, params))
        except (ValueError, TypeError):
            raise SyncError('Invalid Drive JSON response.') from None
        if not isinstance(data, dict) or 'error' in data:
            raise SyncError('Invalid Drive metadata response.')
        return data

    def root(self, folder_id):
        data = self.json('files/' + images.valid_id(folder_id), {'fields': 'id,name,mimeType,trashed', 'supportsAllDrives': 'true'})
        if data.get('id') != folder_id or data.get('mimeType') != FOLDER or data.get('trashed') is not False:
            raise SyncError('Configured source root is not an active readable folder.')
        return data

    def children(self, folder_id):
        images.valid_id(folder_id)
        page, seen = None, set()
        for _ in range(100):
            params = {'q': f"'{folder_id}' in parents and trashed = false", 'pageSize': 1000, 'orderBy': 'name', 'spaces': 'drive', 'supportsAllDrives': 'true', 'includeItemsFromAllDrives': 'true', 'fields': 'nextPageToken,incompleteSearch,files(id,name,mimeType,md5Checksum,modifiedTime,size,version)'}
            if page:
                params['pageToken'] = page
            data = self.json('files', params)
            if data.get('incompleteSearch') or not isinstance(data.get('files'), list):
                raise SyncError('Incomplete Drive folder listing.')
            yield from data['files']
            page = data.get('nextPageToken')
            if not page:
                return
            if not isinstance(page, str) or page in seen:
                raise SyncError('Invalid Drive pagination.')
            seen.add(page)
        raise SyncError('Drive pagination limit exceeded.')

    def download(self, item):
        if int(item.get('size') or 0) > MAX_BYTES:
            raise SyncError('Original exceeds the configured byte limit.')
        data = self.get('files/' + images.valid_id(item['id']), {'alt': 'media', 'supportsAllDrives': 'true'}, MAX_BYTES)
        md5 = item.get('md5Checksum')
        if md5 and (not re.fullmatch('[a-fA-F0-9]{32}', md5) or hashlib.md5(data).hexdigest() != md5.lower()):
            raise SyncError('Original changed during download or has an invalid checksum.')
        return data


def inventory(config, api, old_categories, old_entries, old_state, bindings=None):
    if config.get('version') != 1 or config.get('deleteMissing') is not False:
        raise SyncError('Only version 1 sources with deleteMissing=false are supported.')
    categories = copy.deepcopy(old_categories)
    excluded = dict(old_state.get('excludedFolders', {}))
    folders, files, root_folders, skipped = {}, {}, [], {}
    for source_root in config['roots']:
        root_id = images.valid_id(source_root['folderId'])
        root = api.root(root_id)
        if root.get('name') != 'TimberArt_Designs':
            raise SyncError('Unexpected source root name; verify the configuration.')
        stack = [(root_id, None, None)]
        visited = set()
        while stack:
            parent, top_id, parent_category = stack.pop()
            if parent in visited or len(visited) >= 1000:
                raise SyncError('Duplicate folder or folder limit exceeded.')
            visited.add(parent)
            items = sorted(api.children(parent), key=lambda x: (x.get('name', ''), x.get('id', '')))
            for item in items:
                file_id = images.valid_id(item.get('id'))
                name, mime = item.get('name'), item.get('mimeType')
                if not isinstance(name, str) or not isinstance(mime, str):
                    raise SyncError('Invalid Drive item metadata.')
                if mime == FOLDER:
                    reason = excluded.get(file_id)
                    if file_id in source_root.get('excludeFolderIds', []):
                        reason = 'configured-id'
                    if any(part.casefold() in name.casefold() for part in source_root.get('excludeFolderNamesContaining', [])):
                        reason = 'configured-name'
                    if parent == root_id:
                        root_folders.append({'id': file_id, 'name': name, 'excluded': bool(reason), 'reason': reason})
                    if reason:
                        excluded[file_id] = reason
                        continue
                    if parent != root_id and not source_root.get('recursive', True):
                        continue
                    if file_id in folders or len(folders) >= 999:
                        raise SyncError('Duplicate folder or folder safety limit exceeded.')
                    folders[file_id] = {'folderId': file_id, 'name': name, 'rootFolderId': root_id, 'parentFolderId': parent if parent != root_id else None}
                    stack.append((file_id, top_id or file_id, file_id))
                elif mime in FORMATS and mime in config['imageMimeTypes']:
                    if parent == root_id:
                        # Root files remain excluded by the established source policy.
                        if source_root.get('includeRootImages'):
                            raise SyncError('Use a category subfolder for root images.')
                        continue
                    if file_id in files or len(files) >= 20000:
                        raise SyncError('Duplicate image or image safety limit exceeded.')
                    files[file_id] = {**item, 'folderId': parent, 'topId': top_id, 'rootFolderId': root_id}
                else:
                    skipped[mime] = skipped.get(mime, 0) + 1
    if not root_folders:
        raise SyncError('No readable direct source folders; verify access before proceeding.')
    if len({c['id'] for c in categories}) != len(categories) or len({c['key'] for c in categories}) != len(categories):
        raise SyncError('Duplicate category identity.')
    # Explicit decisions may resolve FIRST bindings only, never change a saved identity.
    by_category_id = {c['id']: c for c in categories}
    for category_id, folder_id in (bindings or {}).items():
        category = by_category_id.get(category_id)
        if not category or folder_id not in folders or category.get('folderId') not in (None, folder_id):
            raise MappingError()
        category['folderId'] = folder_id
    bound = {c['folderId']: c for c in categories if c.get('folderId')}
    if len(bound) != sum(bool(c.get('folderId')) for c in categories):
        raise MappingError()
    for category in categories:
        if category.get('folderId'):
            continue
        evidence = {item['topId'] for fid, item in files.items() if fid in old_entries and old_entries[fid]['category'] == category['key']}
        names = {fid for fid, folder in folders.items() if folder['name'].strip().casefold() == category['name'].strip().casefold()}
        if len(evidence) > 1 or len(names) > 1 or (evidence and names and evidence != names):
            raise MappingError()
        if evidence and not names and any(item['folderId'] != item['topId'] for fid, item in files.items() if fid in old_entries and old_entries[fid]['category'] == category['key']):
            # Before any folder IDs are known, a renamed/moved subtree cannot be
            # distinguished from a move of individual images into another category.
            raise MappingError()
        candidates = evidence or names
        if candidates:
            fid = next(iter(candidates))
            if fid in bound:
                raise MappingError()
            category['folderId'] = fid
            bound[fid] = category
    new = []
    for fid, folder in folders.items():
        if fid not in bound:
            category = {'id': 'drive-' + fid, 'key': 'drive-' + fid, 'name': folder['name'], 'folderId': fid, 'rootFolderId': folder['rootFolderId'], 'parentId': None}
            categories.append(category)
            bound[fid] = category
            new.append(category['id'])
        bound[fid]['name'] = folder['name']
    for fid, folder in folders.items():
        category = bound[fid]
        category['rootFolderId'] = folder['rootFolderId']
        category['parentId'] = bound[folder['parentFolderId']]['id'] if folder['parentFolderId'] else None
    # Stable keys survive renames/moves; generate labels without treating names as paths/code.
    by_id = {c['id']: c for c in categories}
    def label(category, trail=None):
        trail = set() if trail is None else trail
        if category['id'] in trail:
            raise SyncError('Category cycle.')
        parent = by_id.get(category.get('parentId'))
        return (label(parent, trail | {category['id']}) + ' / ' if parent else '') + category['name']
    for category in categories:
        category['displayName'] = label(category)
    public_text(categories)
    report = {'rootFolders': root_folders, 'newCategories': new, 'renamedCategories': [c['id'] for c in categories for old in old_categories if c['id'] == old['id'] and c['name'] != old['name']], 'movedCategories': [c['id'] for c in categories for old in old_categories if c['id'] == old['id'] and c.get('parentId') != old.get('parentId')], 'newImages': sorted(set(files) - set(old_entries)), 'changedImages': sorted(fid for fid, item in files.items() if fid in old_entries and old_entries[fid].get('originalFingerprint') and content_fingerprint(item) != old_entries[fid]['originalFingerprint']), 'verifiedExisting': [], 'unchangedImages': [], 'metadataOnlyImages': [], 'missingImagesRetained': sorted(set(old_entries) - set(files)), 'missingCategoriesRetained': [c['id'] for c in categories if c.get('folderId') not in folders], 'skippedMimeTypes': skipped}
    planned = [item for fid, item in files.items() if not reusable(old_entries.get(fid), item)]
    report['categoryBindings'] = [{k: c.get(k) for k in ('id', 'key', 'name', 'displayName', 'folderId', 'parentId')} for c in categories]
    report['plannedDownloads'] = len(planned)
    report['plannedOriginalBytes'] = sum(int(item.get('size') or 0) for item in planned)
    report['oversizedOriginals'] = [item['id'] for item in planned if int(item.get('size') or 0) > MAX_BYTES]
    return categories, files, bound, {'version': 1, 'excludedFolders': excluded}, report


def content_fingerprint(item):
    if item.get('md5Checksum'):
        return 'md5:' + item['md5Checksum'].lower()
    return 'version:' + str(item.get('version')) if item.get('version') else None


def reusable(old, item):
    fingerprint = content_fingerprint(item)
    return bool(old and fingerprint and old.get('originalFingerprint') == fingerprint and old.get('syncVersion') == SYNC_VERSION and old.get('generator') == images.GENERATOR)


def source_data(item):
    source = images.source_for_id(item['id'])
    source.update({k: item.get(k) for k in ('mimeType', 'modifiedTime', 'size', 'version', 'md5Checksum')})
    source.update({'originalFilename': item['name'], 'rootFolderId': item['rootFolderId'], 'folderIds': [item['folderId']]})
    return source


def screen_source(blob, mime):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(blob)) as source:
                if source.format != FORMATS[mime] or source.width * source.height > MAX_PIXELS or getattr(source, 'n_frames', 1) != 1:
                    raise SyncError('Unsupported, animated or oversized raster image.')
                source.verify()
            with Image.open(io.BytesIO(blob)) as source:
                source.load()
                fmt = source.format
                oriented = ImageOps.exif_transpose(source)
                alpha = oriented.convert('RGBA').getchannel('A') if oriented.mode in ('RGBA', 'LA') or 'transparency' in oriented.info else None
                icc = oriented.info.get('icc_profile')
                if icc:
                    colour = oriented.convert('RGB') if oriented.mode in ('RGBA', 'P', 'PA') else oriented
                    profile = ImageCms.ImageCmsProfile(io.BytesIO(icc))
                    normalized = ImageCms.profileToProfile(colour, profile, ImageCms.createProfile('sRGB'), outputMode='RGB')
                    if alpha is not None:
                        normalized.putalpha(alpha)
                else:
                    normalized = oriented.convert('RGBA' if alpha is not None else 'RGB')
        normalized.info.clear()  # Never propagate EXIF/XMP/comments/profiles to public previews.
        return normalized, fmt
    except SyncError:
        raise
    except Exception:
        raise SyncError('Invalid raster image or unsupported colour profile.') from None


def metadata_record(item, old, category):
    """Shared, in-memory metadata projection; no downloads or writes."""
    entry = copy.deepcopy(old) if old else {}
    entry.update({'id': item['id'], 'name': re.sub(r'\.[^/.]+$', '', item['name']) or item['name'], 'category': category['key'], 'categoryId': category['id'], 'source': source_data(item)})
    entry['sourceFingerprint'] = images.source_fingerprint(entry['source'])
    return entry


def convert_record(item, old, category, api, staged):
    entry = metadata_record(item, old, category)
    old_variants = entry.get('variants', {})
    fingerprint = content_fingerprint(item)
    if reusable(old, item):
        return entry, {}, 'unchanged' if entry == old else 'metadataOnlyImages'
    blob = api.download(item)
    source, fmt = screen_source(blob, item['mimeType'])
    variants, payloads = {}, {}
    for edge in images.EDGES:
        reference = source.copy()
        reference.thumbnail((edge, edge), Image.Resampling.LANCZOS)
        old_meta = old_variants.get(str(edge))
        pixel_hash = images.digest(reference.convert('RGBA').tobytes())
        if old_meta and old_meta['width'] == reference.width and old_meta['height'] == reference.height and old_meta['pixelSha256'] == pixel_hash:
            variants[str(edge)] = copy.deepcopy(old_meta)
        else:
            payload, meta = images.make_variant(source, edge)
            path = f"assets/motifs/{item['id']}/{edge}-{meta['sha256'][:16]}.webp"
            variants[str(edge)] = {'path': path, **meta}
            existing = images.asset_path(staged, path)
            if existing.exists() and existing.read_bytes() != payload:
                raise SyncError('Asset hash collision or corrupted existing asset.')
            payloads[path] = payload
    entry.update({'variants': variants, 'syncVersion': SYNC_VERSION, 'originalFingerprint': fingerprint, 'sourceFingerprint': images.source_fingerprint(entry['source']), 'previewSource': {'kind': 'Authenticated read-only raster source; never published', 'sha256': images.digest(blob), 'bytes': len(blob), 'mimeType': item['mimeType'], 'format': fmt, 'width': source.width, 'height': source.height}, 'generator': images.GENERATOR})
    action = 'newImages' if old is None else ('changedImages' if variants != old_variants else 'verifiedExisting')
    return entry, payloads, action


def validate_categories(root):
    data = images.read_json(root / 'data/categories.json')
    categories = data['categories']
    if data.get('version') != 1 or len({c['id'] for c in categories}) != len(categories) or len({c['key'] for c in categories}) != len(categories):
        raise SyncError('Invalid categories manifest.')
    keys, ids = {c['key'] for c in categories}, {c['id'] for c in categories}
    baseline = images.read_json(root / 'data/motifs-baseline.json')['motifs']
    if not {m['category'] for m in baseline}.issubset(keys):
        raise SyncError('A baseline category was removed.')
    folder_ids = [c['folderId'] for c in categories if c.get('folderId')]
    if len(folder_ids) != len(set(folder_ids)):
        raise SyncError('Two categories share a folder identity.')
    by_id = {c['id']: c for c in categories}
    for c in categories:
        images.valid_id(c['id'])
        if not isinstance(c['key'], str) or not isinstance(c['name'], str) or not c['name'].strip() or not isinstance(c.get('displayName', c['name']), str):
            raise SyncError('Invalid category labels.')
        if c['key'] not in {m['category'] for m in baseline} and (not c.get('folderId') or c['key'] != 'drive-' + c['folderId'] or c['id'] != c['key']):
            raise SyncError('New category does not use a stable folder identity.')
        trail, cursor = set(), c
        while cursor:
            if cursor['id'] in trail:
                raise SyncError('Category parent cycle.')
            trail.add(cursor['id'])
            cursor = by_id.get(cursor.get('parentId'))
        if c.get('folderId'):
            images.valid_id(c['folderId'])
        if c.get('parentId') and c['parentId'] not in ids:
            raise SyncError('Unknown parent category.')
    for entry in images.read_json(root / 'data/motifs-manifest.json')['motifs']:
        if entry['category'] not in keys or (entry.get('categoryId') and (entry['categoryId'] not in ids or by_id[entry['categoryId']]['key'] != entry['category'])):
            raise SyncError('Unknown motif category.')
    public_text(data)
    return len(categories)


def synchronize(root, api, apply=False, bindings=None):
    """A full scan must succeed before any repository output is changed."""
    root = root.resolve()
    manifest = images.read_json(root / 'data/motifs-manifest.json')
    old_entries = {m['id']: m for m in manifest['motifs']}
    old_categories = images.read_json(root / 'data/categories.json')['categories']
    config = images.read_json(root / 'motifs.sources.json')
    state = images.read_json(root / 'data/drive-sync-state.json', {'version': 1, 'excludedFolders': {}})
    categories, files, bound, state, report = inventory(config, api, old_categories, old_entries, state, bindings)
    public_text(report)
    public_manifest(manifest)
    if not apply:
        report['mode'] = 'inventory'
        report['unchangedImages'] = sorted(fid for fid, item in files.items() if fid in old_entries and reusable(old_entries[fid], item))
        report['unverifiedExisting'] = sorted(fid for fid in files if fid in old_entries and not old_entries[fid].get('originalFingerprint'))
        public_text(report)
        return report
    report['changedImages'] = []
    # Validate every existing asset before allowing reuse (including those not visible on Drive).
    images.validate(root)
    validate_categories(root)
    entries, payloads = copy.deepcopy(old_entries), {}
    for file_id, item in files.items():
        try:
            entry, new_payloads, action = convert_record(item, old_entries.get(file_id), bound[item['folderId']], api, root)
        except Exception as error:
            # IDs, file names and even exception text may contain private source data.
            raise SyncError('Image import failed. No outputs applied; inspect the source privately.') from None
        entries[file_id] = entry
        payloads.update(new_payloads)
        if action == 'unchanged':
            report['unchangedImages'].append(file_id)
        elif action != 'newImages':
            report[action].append(file_id)
    new_manifest = {**manifest, 'motifs': list(entries.values())}
    if new_manifest != manifest:
        from datetime import datetime, timezone
        new_manifest['generatedAt'] = datetime.now(timezone.utc).isoformat()
    if sum(v['bytes'] for e in entries.values() for v in e['variants'].values()) > MAX_REFERENCED_BYTES:
        raise SyncError('Referenced preview budget of 512 MiB exceeded.')
    physical_bytes = sum(p.stat().st_size for p in (root / 'assets/motifs').rglob('*.webp'))
    physical_bytes += sum(len(data) for path, data in payloads.items() if not (root / path).exists())
    if physical_bytes > MAX_SITE_ASSET_BYTES:
        raise SyncError('Total preview asset budget of 800 MiB exceeded; manual cleanup required.')
    public_manifest(new_manifest)
    outputs = {'catalog.json': images.json_bytes(images.build_catalog(list(entries.values()))), 'data/motifs-manifest.json': images.json_bytes(new_manifest), 'data/categories.json': images.json_bytes({'version': 1, 'categories': categories}), 'data/drive-sync-state.json': images.json_bytes(state)}
    for path, data in outputs.items():
        public_text(json.loads(data))
    # Originals are never written, cached or uploaded. Only sanitized JSON and generated WebP.
    changed = {path: data for path, data in {**payloads, **outputs}.items() if not (root / path).exists() or (root / path).read_bytes() != data}
    previous = {path: (root / path).read_bytes() if (root / path).exists() else None for path in changed}
    try:
        for path, data in changed.items():
            if not allowed_path(path):
                raise SyncError('Unexpected output path.')
            images.atomic_write(root / path, data)
        images.validate(root)
        validate_categories(root)
    except Exception:
        for path, data in previous.items():
            if data is None:
                (root / path).unlink(missing_ok=True)
            else:
                images.atomic_write(root / path, data)
        raise SyncError('Output validation failed; all repository outputs rolled back.') from None
    report.update({'mode': 'prepare-pr', 'changedFiles': sorted(changed), 'retainedOriginalIds': len(old_entries)})
    public_text(report)
    return report


def diagnose_metadata(root, api):
    """Read current catalog/state and Drive metadata. Return ONLY fixed aggregate labels.

    No candidate import, PR seed, media downloads, catalog writes or private exports.
    A metadata-only scan cannot prove preview equality when reuse is unavailable.
    """
    root = root.resolve()
    manifest = images.read_json(root / 'data/motifs-manifest.json')
    public_manifest(manifest)
    validate_categories(root)
    old_entries = {m['id']: m for m in manifest['motifs']}
    old_categories = images.read_json(root / 'data/categories.json')['categories']
    config = images.read_json(root / 'motifs.sources.json')
    state = images.read_json(root / 'data/drive-sync-state.json', {'version': 1, 'excludedFolders': {}})
    categories, files, bound, _, _ = inventory(config, api, old_categories, old_entries, state)
    fields = (
        ('originalFilename', 'Quelldateiname'), ('modifiedTime', 'Aenderungszeit'),
        ('version', 'Dateiversion'), ('md5Checksum', 'Inhaltspruefsumme'),
        ('size', 'Dateigroesse'), ('mimeType', 'Dateityp'),
        ('folderIds', 'Direkter Quellordner'), ('rootFolderId', 'Quellhauptordner'),
        ('provider', 'Quellanbieter'), ('fileId', 'Quellidentitaet'),
        ('originalUrl', 'Quellverweis'),
    )
    counts = {label: 0 for _, label in fields}
    for label in ('Weitere Quellfelder', 'Anzeigename', 'Kategoriezuordnung',
                  'Quell-Fingerprint', 'Gespeicherter Quell-Fingerprint inkonsistent',
                  'Importversion', 'Vorschaugenerator', 'Gespeicherter Inhalts-Fingerprint abweichend oder fehlend'):
        counts[label] = 0
    missing = len(set(old_entries) - set(files))
    changed = metadata_only = unverified = 0
    for mid, old in old_entries.items():
        item = files.get(mid)
        if item is None:
            continue
        expected = metadata_record(item, old, bound[item['folderId']])
        different = expected != old
        changed += different
        can_reuse = reusable(old, item)
        metadata_only += different and can_reuse
        unverified += not can_reuse
        for key, label in fields:
            counts[label] += (old['source'].get(key) != expected['source'].get(key)
                              or (key in old['source']) != (key in expected['source']))
        known = {key for key, _ in fields}
        counts['Weitere Quellfelder'] += ({k:v for k,v in old['source'].items() if k not in known}
                                         != {k:v for k,v in expected['source'].items() if k not in known})
        counts['Anzeigename'] += old.get('name') != expected['name']
        counts['Kategoriezuordnung'] += any(old.get(k) != expected[k] for k in ('category', 'categoryId'))
        counts['Quell-Fingerprint'] += old.get('sourceFingerprint') != expected['sourceFingerprint']
        counts['Gespeicherter Quell-Fingerprint inkonsistent'] += old.get('sourceFingerprint') != images.source_fingerprint(old['source'])
        counts['Gespeicherter Inhalts-Fingerprint abweichend oder fehlend'] += (
            not content_fingerprint(item) or old.get('originalFingerprint') != content_fingerprint(item))
        counts['Importversion'] += old.get('syncVersion') != SYNC_VERSION
        counts['Vorschaugenerator'] += old.get('generator') != images.GENERATOR
    by_id = {c['id']: c for c in categories}
    changed_categories = sum(by_id[c['id']] != c for c in old_categories)
    result = '# Drive-Sync Metadaten-Diagnose\n\nStatus: abgeschlossen; ausschliesslich lesend.\n'
    totals = [
        ('Gepruefte bestehende Motive', len(old_entries)),
        ('Durch Metadaten oder Sichtbarkeit erklaerte Rueckhaltungen', missing + changed),
        ('Im Scan nicht sichtbare bestehende Motive', missing),
        ('Bestehende Motive mit abweichender Metadatenprojektion', changed),
        ('Davon bei wiederverwendbarem Bild nur Metadatenabweichung', metadata_only),
        ('Sichtbare bestehende Motive mit notwendiger Bildverifikation (nicht ausgefuehrt)', unverified),
        ('Bestehende Kategorien mit abweichenden Metadaten', changed_categories),
    ]
    result += ''.join(f'- {label}: {count}\n' for label, count in totals + list(counts.items()))
    result += ('\nFeldzaehlungen koennen dasselbe Motiv mehrfach betreffen. '
               'Nicht sichtbar beweist keine Loeschung: auch Berechtigungen, Ausschluesse oder Dateitypen kommen infrage. '
               'Geaenderte Pruefsummen sind Metadatenbefunde, kein visueller Bildvergleich. '
               'Dies ist eine aktuelle Aufnahme gegen den ausgecheckten Katalog, keine Rekonstruktion eines frueheren Laufs. '
               'Bei notwendiger Bildverifikation bleibt die genaue Importabweichung offen.\n')
    return result


def write_additions_evidence(report, root, destination):
    """Private ephemeral scan evidence; never log or upload it to a public artifact."""
    import subprocess
    root = root.resolve()
    if destination.resolve().is_relative_to(root) or report.get('mode') != 'prepare-pr':
        raise SyncError('Scan evidence requires an outside-repository destination and a completed import.')
    visible = set()
    for key in ('newImages','unchangedImages','changedImages','metadataOnlyImages','verifiedExisting'):
        visible.update(report[key])
    missing = set(report['missingCategoriesRetained'])
    result = subprocess.run(['git','rev-parse','HEAD'],cwd=root,capture_output=True,text=True)
    base = result.stdout.strip()
    if result.returncode or not re.fullmatch('[a-f0-9]{40}',base):
        raise SyncError('Cannot bind scan evidence to a trusted base.')
    evidence = {'version':1,'baseCommit':base,'createdAt':int(time.time()),
                'runId':os.environ.get('GITHUB_RUN_ID','local'),'runAttempt':os.environ.get('GITHUB_RUN_ATTEMPT','local'),
                'manifestSha256':images.digest((root/'data/motifs-manifest.json').read_bytes()),
                'categoriesSha256':images.digest((root/'data/categories.json').read_bytes()),
                'visibleMotifIds':sorted(visible),
                'visibleCategoryIds':sorted(c['id'] for c in report['categoryBindings'] if c['id'] not in missing)}
    images.atomic_write(destination,images.json_bytes(evidence))


def write_report(report, destination):
    """Public output is a closed schema of fixed labels, status and aggregate counts."""
    text = '# Google-Drive-Abgleich\n\n'
    text += 'Keine Löschung, kein automatischer Merge und kein Deployment.\n\n'
    mode = report.get('mode')
    if mode not in ('inventory', 'prepare-pr'):
        raise SyncError('Invalid report mode.')
    text += '- Status: abgeschlossen\n- Modus: ' + mode + '\n'
    for key in ['plannedDownloads', 'oversizedOriginals', 'newCategories', 'renamedCategories', 'movedCategories', 'newImages', 'changedImages', 'verifiedExisting', 'unchangedImages', 'metadataOnlyImages', 'missingImagesRetained', 'missingCategoriesRetained', 'unverifiedExisting']:
        if key in report:
            value = report[key]
            count = len(value) if isinstance(value, list) else value
            if type(count) is not int or count < 0:
                raise SyncError('Invalid report count.')
            text += f'- {key}: {count}\n'
    roots = report.get('rootFolders', [])
    text += f'- Direkte Unterordner: {len(roots)}\n'
    text += f'- Ausgeschlossene direkte Unterordner: {sum(bool(item.get("excluded")) for item in roots)}\n'
    text += '\nZuordnungsdetails ausschliesslich privat pruefen. Keine Quelldaten in diesem Bericht.\n'
    Path(destination).write_text(text, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--apply', action='store_true', help='Prepare sanitized outputs; never push/merge/deploy')
    mode.add_argument('--diagnose-metadata', action='store_true', help='Read-only metadata diagnosis; aggregate causes only')
    parser.add_argument('--category-bindings', type=Path, help='Private local-only first bindings JSON outside the repository')
    parser.add_argument('--additions-evidence', type=Path, help='Private ephemeral scan evidence outside repository; never upload')
    parser.add_argument('--report', type=Path, required=True, help='Outside the repository, e.g. RUNNER_TEMP/report.md')
    args = parser.parse_args()
    try:
        if args.report.resolve().is_relative_to(args.repo.resolve()):
            raise SyncError('Report must be outside the repository.')
        if args.additions_evidence and (not args.apply or args.additions_evidence.resolve().is_relative_to(args.repo.resolve()) or args.additions_evidence.resolve() == args.report.resolve()):
            raise SyncError('Private scan evidence needs a separate outside-repository path and apply mode.')
        if args.diagnose_metadata and (args.category_bindings or args.additions_evidence):
            raise SyncError('Diagnosis cannot use binding overrides or import evidence.')
        bindings = load_category_bindings(args.category_bindings, args.repo) if args.category_bindings else None
        api = DriveAPI(os.environ.get('TIMBERART_DRIVE_ACCESS_TOKEN'))
        if args.diagnose_metadata:
            summary = diagnose_metadata(args.repo, api)
            args.report.write_text(summary, encoding='utf-8')
            print('Read-only metadata diagnosis completed; aggregate report only.')
            return 0
        report = synchronize(args.repo, api, args.apply, bindings)
        write_report(report, args.report)
        if args.additions_evidence:
            write_additions_evidence(report, args.repo, args.additions_evidence)
        print('Read-only Drive scan completed; report written outside the repository. No push or deployment.')
        return 0
    except Exception as error:
        # Never emit exception text: API, decoder and validation errors can contain IDs.
        message = MAPPING_ERROR if isinstance(error, MappingError) else 'Drive sync failed; no success declared. Review access and source data privately.'
        print('::error::' + message, file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
