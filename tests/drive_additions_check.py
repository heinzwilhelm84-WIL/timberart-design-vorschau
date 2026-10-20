"""Offline additions-only publication contracts; Drive and GitHub are never contacted."""
import copy
import io
import json
import os
import pathlib
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tools'), str(ROOT/'tests')]
import drive_sync_additions as additions
import drive_sync as sync
import drive_sync_guard as guard
import sync_motifs as images
from drive_sync_check import fixture, blob, image, folder, snapshot, write


class AdditionsChecks(unittest.TestCase):
 def setUp(self):
  self.run_env=patch.dict(os.environ,{'GITHUB_RUN_ID':'123','GITHUB_RUN_ATTEMPT':'1'}); self.run_env.start(); self.addCleanup(self.run_env.stop)
  self.temp = tempfile.TemporaryDirectory(); self.root = pathlib.Path(self.temp.name)/'repo'; self.api = fixture(self.root)
  initial=sync.synchronize(self.root,self.api,True)
  self.git('init','-b','main'); self.git('config','user.name','Offline'); self.git('config','user.email','offline@example.invalid')
  (self.root/'app.js').write_text('trusted application code')
  self.git('add','.'); self.git('commit','-qm','verified main'); self.base = self.git('rev-parse','HEAD')
  self.original = snapshot(self.root)
  self.evidence=pathlib.Path(self.temp.name)/'evidence.json'
  sync.write_additions_evidence(initial,self.root,self.evidence)
 def tearDown(self): self.temp.cleanup()
 def git(self,*args): return subprocess.check_output(['git',*args],cwd=self.root,stderr=subprocess.DEVNULL).decode().strip()
 def sync(self):
  report=sync.synchronize(self.root,self.api,True)
  sync.write_additions_evidence(report,self.root,self.evidence)
  return report
 def add(self,mid='new',parent='a'):
  data = blob('green'); self.api.tree[parent].append(image(mid,mid+'.png',data)); self.api.payloads[mid] = data
 def project(self): return additions.project(self.root,self.evidence)
 def apply_projection(self,payloads):
  target = pathlib.Path(self.temp.name)/'projected'
  for path,data in self.original.items(): images.atomic_write(target/path,data)
  for path,data in payloads.items(): images.atomic_write(target/path,data)
  guard.validate_public(target)
  return target
 def env(self):
  return {'TIMBERART_AUTO_ADDITIONS_ARMED':'true','TIMBERART_AUTO_ADDITIONS_ENABLED':'true',
          'GITHUB_REPOSITORY':guard.REPOSITORY,'GITHUB_REPOSITORY_ID':'1425353605',
          'GITHUB_REF':'refs/heads/main','GITHUB_EVENT_NAME':'schedule','GITHUB_SHA':self.base,'GH_TOKEN':'OFFLINE-JOB-TOKEN','GITHUB_RUN_ID':'123','GITHUB_RUN_ATTEMPT':'1'}
 def context_git(self,root,*args,**kwargs):
  if args[:3] == ('remote','get-url','origin'): return 'https://github.com/'+guard.REPOSITORY+'.git'
  if args[0] == 'ls-remote': return self.base+'\trefs/heads/main'
  return self.real_guard_git(root,*args,**kwargs)
 def test_unchanged_scan_is_empty_and_never_downloads_again(self):
  self.api.downloads=[]; self.sync(); before=snapshot(self.root)
  payloads,counts=self.project()
  self.assertEqual(payloads,{}); self.assertEqual(self.api.downloads,[]); self.assertEqual(before,snapshot(self.root))
  self.assertEqual(counts,dict(newImages=0,newCategories=0,manualImages=0,manualCategories=0))
 def test_new_motif_and_nested_empty_folders_are_additions_only(self):
  self.api.tree['a'].append(folder('nested','Neue Kategorie')); self.api.tree['nested']=[folder('empty','Leer')]; self.api.tree['empty']=[]
  self.add(parent='nested'); self.sync(); before=snapshot(self.root)
  payloads,counts=self.project(); target=self.apply_projection(payloads)
  self.assertEqual(counts['newImages'],1); self.assertEqual(counts['newCategories'],2)
  entries=images.read_json(target/'data/motifs-manifest.json')['motifs']
  self.assertEqual(entries[0],json.loads(self.original['data/motifs-manifest.json'])['motifs'][0])
  self.assertEqual({e['id'] for e in entries},{'old','new'}); self.assertEqual(before,snapshot(self.root))
  self.assertEqual(sum(p.endswith('.webp') for p in payloads),2)
  self.assertNotIn('data/drive-sync-state.json',payloads)
 def test_mixed_replacement_and_new_image_keep_existing_record_and_assets_exact(self):
  data=blob('blue'); self.api.payloads['old']=data; self.api.tree['a'][0]=image('old','Alt.png',data)
  self.add(); self.sync(); payloads,counts=self.project(); target=self.apply_projection(payloads)
  self.assertEqual(counts['manualImages'],1); self.assertEqual(counts['newImages'],1)
  self.assertEqual(images.read_json(target/'data/motifs-manifest.json')['motifs'][0],json.loads(self.original['data/motifs-manifest.json'])['motifs'][0])
  self.assertTrue(all(not p.startswith('assets/motifs/old/') for p in payloads))
 def test_existing_name_time_version_and_category_reassignment_are_never_automatic(self):
  self.api.tree['a'][0].update(name='Renamed.png',modifiedTime='later',version='2'); self.add(); self.sync()
  payloads,counts=self.project(); target=self.apply_projection(payloads)
  self.assertEqual(counts['manualImages'],1); self.assertEqual(images.read_json(target/'catalog.json')[0]['name'],'Alt')
  # Move an existing motif into a new category: only the empty new category is automatic.
  self.git('reset','--hard','HEAD'); self.git('clean','-fd')
  self.api.tree['root'].append(folder('other','Andere')); self.api.tree['other']=[self.api.tree['a'].pop(0)]; self.api.tree['a']=[]
  self.sync(); payloads,counts=self.project(); target=self.apply_projection(payloads)
  self.assertEqual(images.read_json(target/'catalog.json')[0]['category'],'Bestehend')
  self.assertEqual(counts['newImages'],0); self.assertEqual(counts['manualImages'],1)
 def test_renamed_parent_blocks_descendants_but_unrelated_additions_are_separate(self):
  self.api.tree['root'][0]['name']='Renamed existing'
  self.api.tree['a'].append(folder('child','Child')); self.api.tree['child']=[]; self.add('blocked','child')
  self.api.tree['root'].append(folder('safe','Safe')); self.api.tree['safe']=[]; self.add('allowed','safe')
  self.sync(); payloads,counts=self.project(); target=self.apply_projection(payloads)
  self.assertEqual({e['id'] for e in images.read_json(target/'catalog.json')},{'old','allowed'})
  self.assertEqual({c['id'] for c in images.read_json(target/'data/categories.json')['categories']},{'legacy-fixed','drive-safe'})
  self.assertEqual(counts['manualImages'],1); self.assertEqual(counts['manualCategories'],2)
 def test_moved_existing_folder_blocks_new_images_in_it(self):
  old=self.api.tree['root'].pop(0); self.api.tree['root'].append(folder('parent','Parent')); self.api.tree['parent']=[old]
  self.add(); self.sync(); payloads,counts=self.project(); target=self.apply_projection(payloads)
  self.assertEqual({e['id'] for e in images.read_json(target/'catalog.json')},{'old'})
  self.assertEqual(counts['manualCategories'],1); self.assertEqual(counts['manualImages'],1)
 def test_missing_drive_files_are_retained_and_do_not_become_deletions(self):
  self.api.tree['a']=[]; self.api.tree['root'].append(folder('safe','Safe')); self.api.tree['safe']=[]; self.add('new','safe')
  self.sync(); payloads,_=self.project(); target=self.apply_projection(payloads)
  self.assertEqual({e['id'] for e in images.read_json(target/'catalog.json')},{'old','new'})
 def test_repeated_projection_after_publication_has_no_duplicate_ids_or_payloads(self):
  self.add(); self.sync(); payloads,_=self.project()
  for path,data in payloads.items(): images.atomic_write(self.root/path,data)
  self.git('add','.'); self.git('commit','-qm','published additions')
  self.api.downloads=[]; self.sync(); payloads,counts=self.project()
  self.assertEqual(payloads,{}); self.assertEqual(counts['newImages'],0); self.assertEqual(self.api.downloads,[])
 def test_code_workflows_and_unexpected_paths_fail_closed(self):
  self.add(); self.sync(); (self.root/'app.js').write_text('unexpected code')
  with self.assertRaises(sync.SyncError): self.project()
  self.git('checkout','--','app.js'); (self.root/'.github/workflows').mkdir(parents=True)
  (self.root/'.github/workflows/injected.yml').write_text('unexpected workflow')
  with self.assertRaises(sync.SyncError): self.project()
 def test_existing_preview_overwrite_or_symlink_is_never_published(self):
  path=next((self.root/'assets/motifs').rglob('*.webp')); saved=path.read_bytes(); path.write_bytes(b'bad')
  with self.assertRaises(Exception): self.project()
  path.unlink(); other=self.root.parent/'external'; other.write_bytes(saved); path.symlink_to(other)
  with self.assertRaises(Exception): self.project()
 def test_invalid_container_quality_secrets_and_exclusions_fail_closed(self):
  for data in [b'not a webp',b'RIFF'+b'\0'*20]:
   with self.assertRaises(sync.SyncError): additions.lossless_preview(data)
  self.add(); self.sync(); entry=images.read_json(self.root/'data/motifs-manifest.json')['motifs'][-1]
  entry['variants']['600']['losslessVerified']=False
  manifest=images.read_json(self.root/'data/motifs-manifest.json'); manifest['motifs'][-1]=entry
  write(self.root,'data/motifs-manifest.json',manifest)
  with self.assertRaises(sync.SyncError): self.project()
 def test_removed_ids_categories_and_duplicate_mappings_fail_closed(self):
  self.add(); self.sync()
  manifest=images.read_json(self.root/'data/motifs-manifest.json')
  manifest['motifs']=manifest['motifs'][1:]
  write(self.root,'data/motifs-manifest.json',manifest); write(self.root,'catalog.json',images.build_catalog(manifest['motifs']))
  with self.assertRaises(Exception): self.project()
 def test_new_image_wrong_folder_or_fingerprint_cannot_be_published(self):
  self.add(); self.sync(); original=images.read_json(self.root/'data/motifs-manifest.json')
  for change in ['folder','fingerprint','source-id','secret','metadata']:
   manifest=copy.deepcopy(original); entry=manifest['motifs'][-1]
   if change=='folder':
    entry['source']['folderIds']=['not-the-category']; entry['sourceFingerprint']=images.source_fingerprint(entry['source'])
   elif change=='fingerprint': entry['sourceFingerprint']='invalid'
   elif change=='source-id': entry['source']['fileId']='old'
   elif change=='secret': entry['name']='ghp_'+'A'*40
   else: entry['credentials_json']='not public'
   write(self.root,'data/motifs-manifest.json',manifest); write(self.root,'catalog.json',images.build_catalog(manifest['motifs']))
   with self.subTest(change=change),self.assertRaises(Exception): self.project()
 def test_excluded_folder_names_and_ids_are_rejected_even_in_imported_candidate(self):
  self.api.tree['root'].append(folder('safe','Safe')); self.api.tree['safe']=[]; self.sync()
  for change in ['name','id']:
   categories=images.read_json(self.root/'data/categories.json')
   if change=='name': categories['categories'][-1]['name']='LOGO-private'
   else:
    categories['categories'][-1]['name']='Safe'
    write(self.root,'data/drive-sync-state.json',{'version':1,'excludedFolders':{'safe':'configured-id'}})
    self.git('add','data/drive-sync-state.json'); self.git('commit','-qm','persist exclusion')
   write(self.root,'data/categories.json',categories)
   evidence=json.loads(self.evidence.read_text()); evidence.update(baseCommit=self.git('rev-parse','HEAD'),categoriesSha256=images.digest((self.root/'data/categories.json').read_bytes())); self.evidence.write_text(json.dumps(evidence))
   with self.subTest(change=change),self.assertRaises(sync.SyncError): self.project()
 def test_main_race_and_wrong_remote_are_rejected_before_any_push(self):
  self.real_guard_git=guard.git
  for wrong in ['remote','main']:
   def checked(root,*args,**kwargs):
    if args[:3]==('remote','get-url','origin') and wrong=='remote': return 'https://elsewhere.invalid/repo'
    if args[0]=='ls-remote' and wrong=='main': return 'f'*40+'\trefs/heads/main'
    return self.context_git(root,*args,**kwargs)
   with self.subTest(wrong=wrong),patch.dict(os.environ,self.env(),clear=True),patch.object(guard,'git',side_effect=checked):
    with self.assertRaises(sync.SyncError): additions.publish(self.root,self.evidence)
 def test_pending_new_image_removed_from_drive_is_never_automatically_published(self):
  self.add(); self.sync()  # Imported into a pending PR, absent from trusted main.
  self.api.tree['a']=self.api.tree['a'][:1]; report=self.sync()
  self.assertIn('new',report['missingImagesRetained'])
  payloads,counts=self.project(); self.assertEqual(payloads,{})
  self.assertEqual(counts['manualImages'],1)
 def test_pending_new_folder_removed_from_drive_stays_manual(self):
  self.api.tree['root'].append(folder('pending','Pending')); self.api.tree['pending']=[]; self.add('pending-image','pending'); self.sync()
  self.api.tree['root']=self.api.tree['root'][:-1]; self.sync()
  payloads,counts=self.project(); self.assertEqual(payloads,{})
  self.assertEqual(counts['manualImages'],1); self.assertEqual(counts['manualCategories'],1)
 def test_missing_stale_and_in_repository_evidence_fail_closed(self):
  self.add(); self.sync()
  with self.assertRaises(sync.SyncError): additions.project(self.root)
  with self.assertRaises(sync.SyncError): additions.project(self.root,self.root/'evidence.json')
  evidence=json.loads(self.evidence.read_text()); evidence['baseCommit']='f'*40; self.evidence.write_text(json.dumps(evidence))
  with self.assertRaises(sync.SyncError): self.project()
 def test_scan_evidence_cannot_be_replayed_from_another_run_attempt_or_old_scan(self):
  original=json.loads(self.evidence.read_text())
  for change in [{'runId':'another'},{'runAttempt':'2'},{'createdAt':0},{'createdAt':99999999999}]:
   self.evidence.write_text(json.dumps({**original,**change}))
   with self.subTest(change=change),self.assertRaises(sync.SyncError): self.project()
 def test_unauthorized_context_fails_before_network_or_writes(self):
  for change in [{'TIMBERART_AUTO_ADDITIONS_ARMED':'false'},{'TIMBERART_AUTO_ADDITIONS_ENABLED':''},{'GITHUB_EVENT_NAME':'workflow_dispatch'},
                 {'GITHUB_REF':'refs/heads/feature/test'},{'GITHUB_REPOSITORY':'other/repo'},{'GITHUB_REPOSITORY_ID':'1'},{'GITHUB_SHA':'f'*40}]:
   with self.subTest(change=change),patch.dict(os.environ,{**self.env(),**change},clear=True),patch.object(guard,'git',wraps=guard.git) as calls:
    with self.assertRaises(sync.SyncError): additions.publish(self.root,self.evidence)
    self.assertFalse(any(c.args[1]=='ls-remote' for c in calls.call_args_list))
 def test_published_commit_contains_only_projected_data_and_preserves_manual_candidate(self):
  data=blob('blue'); self.api.payloads['old']=data; self.api.tree['a'][0]=image('old','Alt.png',data); self.add(); self.sync()
  candidate=(self.root/'catalog.json').read_bytes(); original_run=subprocess.run; pushes=[]
  def run(args,*a,**kw):
   if args[:2]==['git','push']:
    pushes.append((args,kw)); return subprocess.CompletedProcess(args,0,b'',b'')
   return original_run(args,*a,**kw)
  self.real_guard_git=guard.git
  with patch.dict(os.environ,self.env(),clear=True),patch.object(guard,'git',side_effect=self.context_git),patch.object(subprocess,'run',side_effect=run):
   commit,counts=additions.publish(self.root,self.evidence)
  self.assertEqual(self.git('rev-parse','HEAD'),commit); self.assertEqual(self.git('rev-parse','HEAD^'),self.base)
  self.assertEqual((self.root/'catalog.json').read_bytes(),candidate)
  published=json.loads(self.git('show','HEAD:data/motifs-manifest.json'))['motifs']
  self.assertEqual(published[0],json.loads(self.original['data/motifs-manifest.json'])['motifs'][0])
  self.assertEqual({e['id'] for e in published},{'old','new'})
  self.assertEqual(self.git('show','HEAD:app.js'),'trusted application code')
  self.assertEqual(len(pushes),1); self.assertNotIn('--force',pushes[0][0]); self.assertTrue(pushes[0][0][-1].endswith(':refs/heads/main'))
  self.assertNotIn('OFFLINE-JOB-TOKEN',' '.join(pushes[0][0]))
  self.assertEqual(counts['manualImages'],1)
 def test_push_rejection_leaves_candidate_and_head_unchanged(self):
  self.add(); self.sync(); before=snapshot(self.root); original_run=subprocess.run
  def run(args,*a,**kw):
   if args[:2]==['git','push']: return subprocess.CompletedProcess(args,1,b'',b'PRIVATE ERROR')
   return original_run(args,*a,**kw)
  self.real_guard_git=guard.git
  with patch.dict(os.environ,self.env(),clear=True),patch.object(guard,'git',side_effect=self.context_git),patch.object(subprocess,'run',side_effect=run):
   with self.assertRaises(sync.SyncError) as error: additions.publish(self.root,self.evidence)
  self.assertNotIn('PRIVATE',str(error.exception)); self.assertEqual(self.git('rev-parse','HEAD'),self.base); self.assertEqual(before,snapshot(self.root))
 def test_actual_git_push_rejects_concurrent_main_commit(self):
  self.add(); self.sync(); original_run=subprocess.run; self.real_guard_git=guard.git
  bare=pathlib.Path(self.temp.name)/'remote.git'
  subprocess.run(['git','init','--bare',str(bare)],capture_output=True,check=True)
  subprocess.run(['git','push',str(bare),self.base+':refs/heads/main'],cwd=self.root,capture_output=True,check=True)
  concurrent=self.git('commit-tree',self.git('rev-parse',self.base+'^{tree}'),'-p',self.base,'-m','concurrent main')
  def run(args,*a,**kw):
   if args[:2]==['git','push']:
    original_run(['git','push',str(bare),concurrent+':refs/heads/main'],cwd=self.root,capture_output=True,check=True)
    args=list(args); args[args.index('origin')]=str(bare)
   return original_run(args,*a,**kw)
  with patch.dict(os.environ,self.env(),clear=True),patch.object(guard,'git',side_effect=self.context_git),patch.object(subprocess,'run',side_effect=run):
   with self.assertRaises(sync.SyncError): additions.publish(self.root,self.evidence)
  remote=subprocess.check_output(['git','--git-dir='+str(bare),'rev-parse','refs/heads/main'],text=True).strip()
  self.assertEqual(remote,concurrent); self.assertEqual(self.git('rev-parse','HEAD'),self.base)
 def test_evidence_is_private_count_report_never_contains_observed_ids(self):
  report=self.sync(); evidence=json.loads(self.evidence.read_text())
  self.assertEqual(evidence['visibleMotifIds'],['old']); self.assertEqual(evidence['visibleCategoryIds'],['legacy-fixed'])
  public=pathlib.Path(self.temp.name)/'public.md'; sync.write_report(report,public)
  self.assertNotIn('legacy-fixed',public.read_text()); self.assertNotIn('Alt.png',public.read_text())
  with self.assertRaises(sync.SyncError): sync.write_additions_evidence(report,self.root,self.root/'private.json')
 def test_evidence_and_public_report_path_collision_aborts_before_drive_access(self):
  report=pathlib.Path(self.temp.name)/'public.md'
  for args in [ ['--apply','--additions-evidence',str(report)],['--additions-evidence',str(self.evidence)] ]:
   with patch.object(sys,'argv',['sync','--repo',str(self.root),'--report',str(report),*args]),patch.object(sync,'DriveAPI') as api:
    self.assertEqual(sync.main(),1); api.assert_not_called()
   self.assertFalse(report.exists())
 def test_cli_reports_only_counts_and_generic_errors(self):
  self.add(); self.sync(); out,err=io.StringIO(),io.StringIO()
  import contextlib
  with patch.object(sys,'argv',['additions','--repo',str(self.root),'--evidence',str(self.evidence)]),contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
   self.assertEqual(additions.main(),0)
  self.assertNotIn('Alt',out.getvalue()); self.assertNotIn('legacy-fixed',out.getvalue()); self.assertIn('newImages: 1',out.getvalue())


class PagesWorkflowChecks(unittest.TestCase):
 def execute(self,pages=None,main=None,status='built'):
  import yaml,contextlib
  workflow=yaml.load((ROOT/'.github/workflows/drive-motifs-sync.yml').read_text(),Loader=yaml.BaseLoader)
  step=workflow['jobs']['publish-pages-additions']['steps'][0]['run']
  source='\n'.join(step.splitlines()[1:-1]); calls=[]; expected='a'*40
  def command(args,**kwargs):
   method,path=args[3],args[4]; calls.append((method,path))
   if path.endswith('/pages'): data=pages if pages is not None else {'build_type':'legacy','source':{'branch':'main','path':'/'}}
   elif '/git/ref/' in path: data={'object':{'sha':main or expected}}
   elif method=='POST': data={'status':'queued'}
   else: data={'status':status,'commit':expected}
   return subprocess.CompletedProcess(args,0,json.dumps(data).encode(),b'')
  error=None
  with patch.dict(os.environ,{'VERIFIED_DATA_COMMIT':expected},clear=True),patch.object(subprocess,'run',side_effect=command),patch('time.sleep'),contextlib.redirect_stdout(io.StringIO()):
   try: exec(compile(source,'trusted-workflow-pages','exec'),{})
   except SystemExit as e:error=str(e)
  return calls,error
 def test_expected_data_commit_requests_and_confirms_legacy_build(self):
  calls,error=self.execute(); self.assertIsNone(error)
  self.assertEqual(sum(method=='POST' for method,path in calls),1)
  self.assertTrue(calls[-1][1].endswith('/pages/builds/latest'))
 def test_different_pages_source_or_advanced_main_never_requests_build(self):
  for kwargs in [{'pages':{'build_type':'workflow','source':{'branch':'main','path':'/'}}},{'pages':{'build_type':'legacy','source':{'branch':'other','path':'/'}}},{'main':'b'*40}]:
   with self.subTest(kwargs=kwargs):
    calls,error=self.execute(**kwargs); self.assertIsNotNone(error); self.assertFalse(any(m=='POST' for m,p in calls))
 def test_pages_failure_and_timeout_do_not_claim_success_or_retry_post(self):
  for status in ['errored','queued']:
   with self.subTest(status=status):
    calls,error=self.execute(status=status); self.assertIsNotNone(error); self.assertEqual(sum(m=='POST' for m,p in calls),1)


if __name__ == '__main__':
 with patch.object(socket,'create_connection',side_effect=AssertionError('Offline tests must not connect')):
  unittest.main()
