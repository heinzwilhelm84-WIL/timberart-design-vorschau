#!/usr/bin/env python3
"""Allowlist-only handling of generated data. Never execute code from the bot branch."""
import argparse
import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import drive_sync as sync
import sync_motifs as images

REPOSITORY = 'heinzwilhelm84-WIL/timberart-design-vorschau'
BRANCH = 'bot/drive-motifs-sync'


def git(root, *args, binary=False):
    result = subprocess.run(['git', *args], cwd=root, capture_output=True)
    if result.returncode:
        raise sync.SyncError('Git data operation failed; no publication permitted.')
    return result.stdout if binary else result.stdout.decode().strip()


def three_way(base, current, pending, key='id'):
    """Preserve additions from main and the pending PR, fail on concurrent edits."""
    maps = [{entry[key]: entry for entry in entries} for entries in (base, current, pending)]
    if any(len(m) != len(entries) for m, entries in zip(maps, (base, current, pending))):
        raise sync.SyncError('Duplicate identity in pending sync data.')
    b, c, p = maps
    if set(b) - set(c) or set(b) - set(p):
        raise sync.SyncError('Pending/main data removes an existing identity.')
    result = copy.deepcopy(c)
    for identity, record in p.items():
        if identity in c and c[identity] != b.get(identity) and record != b.get(identity) and c[identity] != record:
            raise sync.SyncError('Concurrent generated-data edit; review/rebase the sync PR manually.')
        if record != b.get(identity):
            result[identity] = copy.deepcopy(record)
    return list(result.values())


def validate_public(root):
    sync.public_manifest(images.read_json(root / 'data/motifs-manifest.json'))
    result = images.validate(root)
    sync.validate_categories(root)
    if result['bytes'] > sync.MAX_REFERENCED_BYTES:
        raise sync.SyncError('Referenced preview budget of 512 MiB exceeded.')
    if sum(p.stat().st_size for p in (root / 'assets/motifs').rglob('*.webp')) > sync.MAX_SITE_ASSET_BYTES:
        raise sync.SyncError('Total preview asset budget of 800 MiB exceeded.')
    for path in sync.PUBLIC_FILES:
        p = root / path
        if p.exists():
            data = images.read_json(p)
            sync.public_text(data)
            if path.endswith('drive-sync-state.json'):
                if set(data) != {'version', 'excludedFolders'} or data['version'] != 1:
                    raise sync.SyncError('Unexpected sync state schema.')
                for fid, reason in data['excludedFolders'].items():
                    images.valid_id(fid)
                    if reason not in ('configured-id', 'configured-name'):
                        raise sync.SyncError('Unexpected exclusion reason.')
    return result


def changed_paths(root):
    tracked = git(root, 'diff', '--name-only', '-z', 'HEAD', binary=True).decode().split('\0')
    untracked = git(root, 'ls-files', '--others', '--exclude-standard', '-z', binary=True).decode().split('\0')
    paths = sorted(set(filter(None, tracked + untracked)))
    for path in paths:
        if not sync.allowed_path(path) or not (root / path).is_file() or (root / path).is_symlink():
            raise sync.SyncError('Unexpected/deleted output path; refusing PR publication.')
        if path.endswith('.webp'):
            # A generated filename must actually refer to a stripped WebP image.
            from PIL import Image
            with Image.open(root / path) as image:
                if image.format != 'WEBP' or any(k in image.info for k in ('exif', 'xmp', 'icc_profile')):
                    raise sync.SyncError('Non-WebP or private image metadata in output.')
        else:
            sync.public_text(images.read_json(root / path))
    return paths


def seed_pending(root):
    # Query only PR metadata, never dispatch a workflow. The CLI token is the job token.
    result = subprocess.run(['gh', 'pr', 'list', '--repo', REPOSITORY, '--head', BRANCH, '--base', 'main', '--state', 'open', '--json', 'number,isCrossRepository,headRefOid'], cwd=root, capture_output=True)
    if result.returncode:
        raise sync.SyncError('Cannot check pending PR; refusing to discard its data.')
    candidates = [pr for pr in json.loads(result.stdout) if pr.get('isCrossRepository') is False]
    if not candidates:
        return False
    if len(candidates) != 1:
        raise sync.SyncError('Ambiguous pending PR; manual review required.')
    # Public repository read; no credentials are installed in git config.
    git(root, 'fetch', '--no-tags', 'origin', 'refs/heads/' + BRANCH)
    pending_ref = git(root, 'rev-parse', 'FETCH_HEAD')
    if candidates[0].get('headRefOid') != pending_ref:
        raise sync.SyncError('Pending branch changed during inspection; rerun before proceeding.')
    base_ref = git(root, 'merge-base', 'HEAD', pending_ref)
    paths = list(filter(None, git(root, 'diff', '--name-only', '-z', base_ref, pending_ref, binary=True).decode().split('\0')))
    if any(not sync.allowed_path(p) for p in paths):
        raise sync.SyncError('Pending PR contains non-generated files; manual review required.')
    def load(ref, path, default=None):
        result = subprocess.run(['git', 'show', ref + ':' + path], cwd=root, capture_output=True)
        if result.returncode:
            if default is not None:
                return copy.deepcopy(default)
            raise sync.SyncError('Missing pending metadata; automatic deletion refused.')
        data = json.loads(result.stdout)
        sync.public_text(data)
        return data
    current = images.read_json(root / 'data/motifs-manifest.json')
    pending = load(pending_ref, 'data/motifs-manifest.json')
    merged_entries = three_way(load(base_ref, 'data/motifs-manifest.json')['motifs'], current['motifs'], pending['motifs'])
    current_categories = images.read_json(root / 'data/categories.json')
    merged_categories = three_way(load(base_ref, 'data/categories.json')['categories'], current_categories['categories'], load(pending_ref, 'data/categories.json')['categories'])
    state = images.read_json(root / 'data/drive-sync-state.json', {'version': 1, 'excludedFolders': {}})
    state['excludedFolders'].update(load(pending_ref, 'data/drive-sync-state.json', {'version': 1, 'excludedFolders': {}})['excludedFolders'])
    manifest = {**current, 'motifs': merged_entries}
    if merged_entries != current['motifs']:
        manifest['generatedAt'] = pending['generatedAt']
    payloads = {'data/motifs-manifest.json': images.json_bytes(manifest), 'catalog.json': images.json_bytes(images.build_catalog(merged_entries)), 'data/categories.json': images.json_bytes({'version': 1, 'categories': merged_categories}), 'data/drive-sync-state.json': images.json_bytes(state)}
    for path in paths:
        if path.endswith('.webp'):
            # Read as a blob, never extract a git archive or execute pending files.
            mode = git(root, 'ls-tree', pending_ref, '--', path).split(' ', 1)[0]
            if mode != '100644':
                raise sync.SyncError('Pending asset is deleted, executable or a symlink.')
            payloads[path] = git(root, 'show', pending_ref + ':' + path, binary=True)
    previous = {p: (root / p).read_bytes() if (root / p).exists() else None for p in payloads}
    try:
        for path, data in payloads.items():
            images.atomic_write(root / path, data)
        validate_public(root)
        changed_paths(root)
    except Exception:
        for path, data in previous.items():
            if data is None:
                (root / path).unlink(missing_ok=True)
            else:
                images.atomic_write(root / path, data)
        raise sync.SyncError('Pending data rejected and rolled back; no code from the branch executed.') from None
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--seed', action='store_true')
    args = parser.parse_args()
    root = args.repo.resolve()
    try:
        if os.environ.get('GITHUB_REPOSITORY') != REPOSITORY or os.environ.get('GITHUB_REF') != 'refs/heads/main' or os.environ.get('GITHUB_EVENT_NAME') not in ('workflow_dispatch', 'schedule'):
            raise sync.SyncError('Only an approved main workflow in the preview repository is allowed.')
        if args.seed:
            print('Pending generated-data seed:', 'loaded' if seed_pending(root) else 'none')
        else:
            remote_main = git(root, 'ls-remote', 'origin', 'refs/heads/main').split()
            if not remote_main or remote_main[0] != os.environ.get('GITHUB_SHA'):
                raise sync.SyncError('main advanced during the scan; rerun before publishing any PR update.')
            validate_public(root)
            paths = changed_paths(root)
            print('Validated allowlisted generated outputs:', len(paths))
        return 0
    except Exception as error:
        print('::error::' + (str(error) if isinstance(error, sync.SyncError) else 'Generated-data validation failed.'), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
