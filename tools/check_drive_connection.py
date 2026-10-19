#!/usr/bin/env python3
"""Manual connection check: folder metadata GETs only; no image or file content.
No synchronization, credentials files, logs of API payloads, or output artifacts.
Importing this module does not authenticate or make a network request.
"""
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
FOLDER = 'application/vnd.google-apps.folder'
EXPECTED_ROOT_NAME = 'TimberArt_Designs'
MAX_RESPONSE_BYTES = 1024 * 1024
MAX_FOLDERS = 1000
MAX_PAGES_PER_FOLDER = 100
ID_PATTERN = re.compile(r'[A-Za-z0-9_-]{1,200}\Z')


class CheckError(Exception):
    """A deliberately credential-free diagnostic suitable for public logs."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise CheckError('Drive API redirect refused; no credentials forwarded.')


def valid_id(value):
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        raise CheckError('Invalid folder ID in configuration or API response.')
    return value


def configured_root(path):
    try:
        config = json.loads(path.read_text(encoding='utf-8'))
        roots = config['roots']
        if config.get('version') != 1 or not isinstance(roots, list) or len(roots) != 1:
            raise CheckError('This connection check requires exactly one configured Drive root.')
        return valid_id(roots[0]['folderId'])
    except (OSError, ValueError, KeyError, TypeError):
        raise CheckError('Cannot read an unambiguous root from motifs.sources.json.') from None


class DriveMetadata:
    def __init__(self, token, opener=None):
        if not token:
            raise CheckError('No short-lived access token supplied by the auth step.')
        self._token = token
        self._opener = opener or urllib.request.build_opener(NoRedirect())

    def get(self, path, params):
        # The only allowed endpoints are the fixed API host's folder metadata methods.
        if path != 'files' and not (path.startswith('files/') and ID_PATTERN.fullmatch(path[6:])):
            raise CheckError('Non-metadata API path refused.')
        if 'alt' in params:
            raise CheckError('Media requests are prohibited.')
        url = 'https://www.googleapis.com/drive/v3/' + path + '?' + urllib.parse.urlencode(params)
        request = urllib.request.Request(url, method='GET', headers={
            'Authorization': 'Bearer ' + self._token,
            'Accept': 'application/json',
        })
        try:
            with self._opener.open(request, timeout=15) as response:
                body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise CheckError('Drive metadata response exceeds the safety limit.')
            data = json.loads(body)
            if not isinstance(data, dict) or 'error' in data:
                raise CheckError('Drive API returned invalid metadata.')
            return data
        except urllib.error.HTTPError as error:
            # Never print the URL, request headers, response body or raw exception.
            raise CheckError(f'Drive metadata GET failed (HTTP {error.code}); check folder sharing, scope and Drive API enablement.') from None
        except (urllib.error.URLError, OSError):
            raise CheckError('Drive metadata GET failed due to a network/TLS error.') from None
        except (ValueError, TypeError):
            raise CheckError('Drive API response is not valid JSON metadata.') from None


def check_folders(api, root_id):
    valid_id(root_id)
    root = api.get('files/' + root_id, {
        'fields': 'id,name,mimeType,trashed', 'supportsAllDrives': 'true',
    })
    if root.get('id') != root_id or root.get('mimeType') != FOLDER or root.get('trashed') is not False:
        raise CheckError('Configured Drive root is not an accessible, active folder.')
    if root.get('name') != EXPECTED_ROOT_NAME:
        raise CheckError('Configured root name does not match TimberArt_Designs; verify the folder ID before proceeding.')
    queue = [(root_id, 0)]
    seen = {root_id}
    direct, deepest = 0, 0
    for folder_id, depth in queue:
        page_token = None
        tokens = set()
        for _ in range(MAX_PAGES_PER_FOLDER):
            params = {
                'q': f"'{folder_id}' in parents and trashed = false and mimeType = '{FOLDER}'",
                'fields': 'nextPageToken,incompleteSearch,files(id,mimeType)',
                'pageSize': 1000, 'spaces': 'drive',
                'supportsAllDrives': 'true', 'includeItemsFromAllDrives': 'true',
            }
            if page_token:
                params['pageToken'] = page_token
            page = api.get('files', params)
            if page.get('incompleteSearch'):
                raise CheckError('Drive reports an incomplete folder search; no success declared.')
            folders = page.get('files')
            if not isinstance(folders, list):
                raise CheckError('Drive API response has no valid folder list.')
            for child in folders:
                if not isinstance(child, dict) or child.get('mimeType') != FOLDER:
                    raise CheckError('Unexpected non-folder metadata in folder-only search.')
                child_id = valid_id(child.get('id'))
                if child_id in seen:
                    raise CheckError('Duplicate/cyclic folder metadata; no success declared.')
                if len(seen) >= MAX_FOLDERS:
                    raise CheckError('Folder safety limit reached; no success declared.')
                seen.add(child_id)
                queue.append((child_id, depth + 1))
                direct += depth == 0
                deepest = max(deepest, depth + 1)
            page_token = page.get('nextPageToken')
            if not page_token:
                break
            if not isinstance(page_token, str) or page_token in tokens:
                raise CheckError('Invalid/repeated pagination token; no success declared.')
            tokens.add(page_token)
        else:
            raise CheckError('Folder pagination safety limit reached; no success declared.')
    if direct == 0:
        raise CheckError('No readable subfolders found; verify the root and inherited sharing.')
    return {'direct_subfolders': direct, 'all_subfolders': len(seen) - 1, 'max_depth': deepest}


def main():
    try:
        root_id = configured_root(ROOT / 'motifs.sources.json')
        api = DriveMetadata(os.environ.get('TIMBERART_DRIVE_ACCESS_TOKEN'))
        result = check_folders(api, root_id)
    except CheckError as error:
        print('::error::' + str(error), file=sys.stderr)
        return 1
    except Exception:
        print('::error::Unexpected local check error; no API payload or credentials logged.', file=sys.stderr)
        return 1
    print('PASS: authenticated folder-metadata access; TimberArt_Designs matches configuration.')
    print(f"Readable subfolders: {result['direct_subfolders']} direct, {result['all_subfolders']} total; maximum depth {result['max_depth']}.")
    print('No image downloads, Drive writes, synchronization or publication performed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
