#!/usr/bin/env python3
"""Project validated sync outputs onto main as additions only. Publication is disarmed by default."""
import argparse
import base64
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import time

import drive_sync as sync
import drive_sync_guard as guard
import sync_motifs as images


def at_head(root, path, binary=False):
    return guard.git(root, 'show', 'HEAD:' + path, binary=binary) if binary else json.loads(guard.git(root, 'show', 'HEAD:' + path))


def indexed(records):
    result = {r['id']: r for r in records}
    if len(result) != len(records):
        raise sync.SyncError('Duplicate identity; automatic publication refused.')
    return result


def lossless_preview(payload):
    if payload[:4] != b'RIFF' or payload[8:12] != b'WEBP' or len(payload) < 20 or struct.unpack('<I', payload[4:8])[0] != len(payload) - 8:
        raise sync.SyncError('Invalid lossless WebP container.')
    offset, chunks = 12, []
    while offset + 8 <= len(payload):
        kind = payload[offset:offset+4]
        size = struct.unpack('<I', payload[offset+4:offset+8])[0]
        chunks.append(kind)
        offset += 8 + size + size % 2
    if offset != len(payload) or chunks.count(b'VP8L') != 1 or any(c not in (b'VP8X', b'VP8L') for c in chunks):
        raise sync.SyncError('Only stripped, non-animated lossless WebP is eligible.')


def project(root, evidence_path=None):
    """No network or repository writes. Reuse the existing validators and import results."""
    guard.validate_public(root)
    if evidence_path is None or evidence_path.resolve().is_relative_to(root.resolve()):
        raise sync.SyncError('Fresh private scan evidence is required outside the repository.')
    evidence = images.read_json(evidence_path)
    if set(evidence) != {'version','baseCommit','createdAt','runId','runAttempt','manifestSha256','categoriesSha256','visibleMotifIds','visibleCategoryIds'} or evidence['version'] != 1:
        raise sync.SyncError('Unexpected scan evidence schema.')
    if evidence['baseCommit'] != guard.git(root,'rev-parse','HEAD') or evidence['manifestSha256'] != images.digest((root/'data/motifs-manifest.json').read_bytes()) or evidence['categoriesSha256'] != images.digest((root/'data/categories.json').read_bytes()):
        raise sync.SyncError('Stale scan evidence; automatic publication refused.')
    if evidence['runId'] != os.environ.get('GITHUB_RUN_ID','local') or evidence['runAttempt'] != os.environ.get('GITHUB_RUN_ATTEMPT','local') or not isinstance(evidence['createdAt'],int) or not 0 <= time.time()-evidence['createdAt'] <= 3600:
        raise sync.SyncError('Scan evidence is not fresh for this run attempt.')
    for key in ('visibleMotifIds','visibleCategoryIds'):
        if not isinstance(evidence[key],list) or len(set(evidence[key])) != len(evidence[key]):
            raise sync.SyncError('Invalid scan evidence identities.')
        for identity in evidence[key]:
            images.valid_id(identity)
    visible_motifs, visible_categories = set(evidence['visibleMotifIds']), set(evidence['visibleCategoryIds'])
    paths = guard.changed_paths(root)
    for path in paths:
        for parent in (root / path).parents:
            if parent == root:
                break
            if parent.is_symlink():
                raise sync.SyncError('Symlink output directory refused.')
        if path.endswith('.webp') and guard.git(root, 'ls-tree', 'HEAD', '--', path):
            raise sync.SyncError('An existing preview file was modified; automatic publication refused.')
    old = at_head(root, 'data/motifs-manifest.json')
    candidate = images.read_json(root / 'data/motifs-manifest.json')
    if {k:v for k,v in old.items() if k not in ('motifs','generatedAt')} != {k:v for k,v in candidate.items() if k not in ('motifs','generatedAt')}:
        raise sync.SyncError('Manifest schema/generator changed; manual review required.')
    base_entries, proposed = indexed(old['motifs']), indexed(candidate['motifs'])
    old_categories = at_head(root, 'data/categories.json')
    base_categories = indexed(old_categories['categories'])
    categories = indexed(images.read_json(root / 'data/categories.json')['categories'])
    if set(base_entries) - set(proposed) or set(base_categories) - set(categories):
        raise sync.SyncError('Removal or identity replacement detected; automatic publication refused.')
    config = at_head(root, 'motifs.sources.json')
    roots = {r['folderId']: r for r in config['roots']}
    excluded = at_head(root, 'data/drive-sync-state.json')['excludedFolders']
    eligible = {}

    def eligible_category(cid):
        if cid in eligible:
            return eligible[cid]
        category = categories[cid]
        if cid not in visible_categories:
            eligible[cid] = False
            return False
        eligible[cid] = False  # Also fail closed on any unexpected cycle.
        parent = category.get('parentId')
        if parent and not eligible_category(parent):
            return False
        if cid in base_categories:
            eligible[cid] = category == base_categories[cid]
            return eligible[cid]
        allowed = {'id','key','name','displayName','folderId','rootFolderId','parentId'}
        fid, rid = category.get('folderId'), category.get('rootFolderId')
        if set(category) - allowed or not fid or cid != 'drive-' + fid or category['key'] != cid or rid not in roots:
            raise sync.SyncError('New category has ambiguous identity or metadata.')
        rule = roots[rid]
        if fid in excluded or fid in rule.get('excludeFolderIds', []) or any(n.casefold() in category['name'].casefold() for n in rule.get('excludeFolderNamesContaining', [])):
            raise sync.SyncError('Excluded category cannot be published automatically.')
        if parent and categories[parent].get('rootFolderId') != rid:
            raise sync.SyncError('Cross-root category relationship refused.')
        eligible[cid] = True
        return True

    additions_c = [c for cid,c in categories.items() if cid not in base_categories and eligible_category(cid)]
    additions_m, assets = [], {}
    for mid, entry in proposed.items():
        if mid in base_entries:
            continue
        if mid not in visible_motifs:
            continue
        cid = entry.get('categoryId')
        if cid not in categories:
            raise sync.SyncError('New motif lacks an explicit category identity.')
        if not eligible_category(cid):
            continue
        category, source = categories[cid], entry['source']
        if source.get('provider') != 'google-drive' or source.get('folderIds') != [category.get('folderId')] or source.get('rootFolderId') != category.get('rootFolderId'):
            raise sync.SyncError('Ambiguous new motif folder assignment.')
        if entry.get('sourceFingerprint') != images.source_fingerprint(source) or entry.get('syncVersion') != sync.SYNC_VERSION or entry.get('generator') != images.GENERATOR:
            raise sync.SyncError('New motif has not been verified by the current importer.')
        if entry.get('originalFingerprint') != sync.content_fingerprint(source) or not entry.get('originalFingerprint'):
            raise sync.SyncError('New motif lacks verified original metadata.')
        for edge, meta in entry['variants'].items():
            path = meta['path']
            if path != f"assets/motifs/{mid}/{edge}-{meta['sha256'][:16]}.webp" or meta['losslessVerified'] is not True:
                raise sync.SyncError('Unexpected new preview path or quality status.')
            payload = (root / path).read_bytes()
            lossless_preview(payload)
            if guard.git(root, 'ls-tree', 'HEAD', '--', path):
                if at_head(root, path, binary=True) != payload:
                    raise sync.SyncError('Existing asset collision refused.')
            else:
                assets[path] = payload
        additions_m.append(entry)
    entries = old['motifs'] + additions_m
    manifest = {**old, 'motifs': entries}
    if additions_m:
        manifest['generatedAt'] = candidate['generatedAt']
    outputs = {'catalog.json': images.json_bytes(images.build_catalog(entries)),
               'data/motifs-manifest.json': images.json_bytes(manifest),
               'data/categories.json': images.json_bytes({**old_categories, 'categories':old_categories['categories'] + additions_c})}
    # Validate the projected catalog against exactly its referenced assets. No pending code executes.
    with tempfile.TemporaryDirectory(prefix='timberart-additions-') as temporary:
        staged = Path(temporary)
        for path in ('motifs.sources.json','data/motifs-baseline.json','data/drive-sync-state.json'):
            images.atomic_write(staged / path, at_head(root, path, binary=True))
        for path, payload in outputs.items():
            images.atomic_write(staged / path, payload)
        for entry in entries:
            for meta in entry['variants'].values():
                path = meta['path']
                source = root / path
                if source.is_symlink() or any(p.is_symlink() for p in source.parents if p != root):
                    raise sync.SyncError('Symlink preview refused.')
                target = staged / path
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
        guard.validate_public(staged)
    outputs = {p:b for p,b in outputs.items() if at_head(root, p, binary=True) != b}
    if not additions_m and not additions_c:
        outputs = {}
    result = {**assets, **outputs}
    counts = {'newImages':len(additions_m),'newCategories':len(additions_c),
              'manualImages':sum(proposed[k] != v for k,v in base_entries.items()) + len(set(proposed)-set(base_entries))-len(additions_m),
              'manualCategories':sum(categories[k] != v for k,v in base_categories.items()) + len(set(categories)-set(base_categories))-len(additions_c)}
    return result, counts


def publication_context(root):
    expected = os.environ.get('GITHUB_SHA', '')
    if (os.environ.get('TIMBERART_AUTO_ADDITIONS_ARMED') != 'true' or os.environ.get('TIMBERART_AUTO_ADDITIONS_ENABLED') != 'true'
        or os.environ.get('GITHUB_REPOSITORY') != guard.REPOSITORY or os.environ.get('GITHUB_REPOSITORY_ID') != '1425353605'
        or os.environ.get('GITHUB_REF') != 'refs/heads/main' or os.environ.get('GITHUB_EVENT_NAME') != 'schedule'
        or len(expected) != 40 or guard.git(root, 'rev-parse', 'HEAD') != expected):
        raise sync.SyncError('Automatic publication is disabled or outside its trusted context.')
    if guard.git(root, 'remote', 'get-url', 'origin') not in ('https://github.com/'+guard.REPOSITORY, 'https://github.com/'+guard.REPOSITORY+'.git'):
        raise sync.SyncError('Unexpected publication remote.')
    if guard.git(root, 'ls-remote', 'origin', 'refs/heads/main').split()[0] != expected:
        raise sync.SyncError('main advanced; automatic publication refused.')
    return expected


def publish(root, evidence_path=None):
    expected = publication_context(root)  # Before any network operation except trusted main verification.
    payloads, counts = project(root, evidence_path)
    if not payloads:
        return '', counts
    token = os.environ.get('GH_TOKEN')
    if not token:
        raise sync.SyncError('Missing job token; automatic publication refused.')
    with tempfile.TemporaryDirectory(prefix='timberart-index-') as temporary:
        env = {**os.environ, 'GIT_INDEX_FILE':str(Path(temporary)/'index'),
               'GIT_AUTHOR_NAME':'github-actions[bot]', 'GIT_COMMITTER_NAME':'github-actions[bot]',
               'GIT_AUTHOR_EMAIL':'41898282+github-actions[bot]@users.noreply.github.com',
               'GIT_COMMITTER_EMAIL':'41898282+github-actions[bot]@users.noreply.github.com'}
        def command(*args, data=None, auth=False):
            call_env = env.copy()
            if auth:
                header = base64.b64encode(('x-access-token:'+token).encode()).decode()
                call_env.update({'GIT_CONFIG_COUNT':'1','GIT_CONFIG_KEY_0':'http.https://github.com/.extraheader','GIT_CONFIG_VALUE_0':'AUTHORIZATION: basic '+header})
            r = subprocess.run(['git',*args],cwd=root,input=data,capture_output=True,env=call_env)
            if r.returncode:
                raise sync.SyncError('Atomic data publication failed; no automatic retry or force push.')
            return r.stdout.decode().strip()
        command('read-tree',expected)
        for path, payload in payloads.items():
            if not sync.allowed_path(path) or path == 'data/drive-sync-state.json':
                raise sync.SyncError('Non-addition output refused.')
            blob = command('hash-object','-w','--stdin',data=payload)
            command('update-index','--add','--cacheinfo','100644',blob,path)
        tree = command('write-tree')
        commit = command('commit-tree',tree,'-p',expected,'-m','Add verified new Drive motifs and categories')
        if set(command('diff-tree','--no-commit-id','--name-only','-r',commit).splitlines()) != set(payloads):
            raise sync.SyncError('Unexpected commit paths; no push permitted.')
        # Normal fast-forward push: another main commit causes rejection, never force it.
        command('push','--no-follow-tags','origin',commit+':refs/heads/main',auth=True)
    # Preserve the full candidate changes for the manual PR, but base it on the new main.
    guard.git(root,'reset','--mixed',commit)
    return commit, counts


def dry_run_summary(root, evidence_path):
    """Validate the existing projection; report only fixed aggregate counts, never publish."""
    _, eligible = project(root, evidence_path)
    evidence = images.read_json(evidence_path)
    base_m = indexed(at_head(root, 'data/motifs-manifest.json')['motifs'])
    candidate_m = indexed(images.read_json(root / 'data/motifs-manifest.json')['motifs'])
    base_c = indexed(at_head(root, 'data/categories.json')['categories'])
    candidate_c = indexed(images.read_json(root / 'data/categories.json')['categories'])
    new_m, new_c = len(set(candidate_m) - set(base_m)), len(set(candidate_c) - set(base_c))
    visible_m, visible_c = set(evidence['visibleMotifIds']), set(evidence['visibleCategoryIds'])
    counts = [
        ('Neue Kategorien im Kandidaten', new_c),
        ('Neue Motive im Kandidaten', new_m),
        ('Automatisch zulaessige neue Kategorien', eligible['newCategories']),
        ('Automatisch zulaessige neue Motive', eligible['newImages']),
        ('Zurueckgehaltene bestehende Kategorien', sum(candidate_c[k] != v or k not in visible_c for k,v in base_c.items())),
        ('Zurueckgehaltene bestehende Motive', sum(candidate_m[k] != v or k not in visible_m for k,v in base_m.items())),
        ('Zurueckgehaltene neue Kategorien', new_c - eligible['newCategories']),
        ('Zurueckgehaltene neue Motive', new_m - eligible['newImages']),
    ]
    return '\n# Drive-Sync Dry-run\n\nStatus: geprueft; nichts veroeffentlicht.\n' + ''.join(f'- {label}: {count}\n' for label,count in counts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--publish',action='store_true')
    mode.add_argument('--dry-run-summary',action='store_true',help='Validate without publication and report only aggregate counts')
    parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--report',type=Path)
    args = parser.parse_args()
    try:
        root = args.repo.resolve()
        if args.report and (args.report.resolve().is_relative_to(root) or args.report.resolve() == args.evidence.resolve()):
            raise sync.SyncError('Report must be separate from the private evidence and outside the repository.')
        if args.dry_run_summary:
            commit, summary = '', dry_run_summary(root,args.evidence)
        else:
            commit, counts = publish(root,args.evidence) if args.publish else ('', project(root,args.evidence)[1])
            summary = '\n### Additions-only review\n' + ''.join(f'- {key}: {value}\n' for key,value in counts.items())
        print(summary)
        if args.report:
            with args.report.open('w' if args.dry_run_summary else 'a') as report:
                report.write(summary)
        if commit and os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'],'a') as output:
                output.write('published='+commit+'\n')
        return 0
    except Exception:
        print('::error::Additions-only validation/publication failed. Nothing else may be published automatically; inspect privately.',file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
