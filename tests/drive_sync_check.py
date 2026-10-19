"""Offline synchronization contract tests; all Google operations are simulated."""
import copy,hashlib,importlib.util,io,json,pathlib,socket,subprocess,sys,tempfile,unittest
from unittest.mock import patch
from PIL import Image,PngImagePlugin
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import drive_sync as sync
import drive_sync_guard as guard
import sync_motifs as images

FOLDER=sync.FOLDER

def blob(color='red',size=(80,40),mode='RGBA',secret=False):
 im=Image.new(mode,size,color);out=io.BytesIO();info=PngImagePlugin.PngInfo()
 if secret:info.add_text('Author','PRIVATE ORIGINAL AUTHOR')
 im.save(out,format='PNG',pnginfo=info);return out.getvalue()

def folder(id,name):return {'id':id,'name':name,'mimeType':FOLDER}
def image(id,name,data):return {'id':id,'name':name,'mimeType':'image/png','size':str(len(data)),'md5Checksum':hashlib.md5(data).hexdigest(),'version':'1'}

class FakeDrive:
 def __init__(self,tree,payloads=None):self.tree=tree;self.payloads=payloads or {};self.downloads=[];self.reads=[]
 def root(self,id):return {'id':id,'name':'TimberArt_Designs','mimeType':FOLDER,'trashed':False}
 def children(self,id):
  self.reads.append(id)
  if isinstance(self.tree[id],Exception):raise self.tree[id]
  return copy.deepcopy(self.tree[id])
 def download(self,item):self.downloads.append(item['id']);return self.payloads[item['id']]

def write(root,path,data):p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(images.json_bytes(data))
def snapshot(root):return {str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file() and '.git' not in p.parts}

def fixture(root):
 data=blob();record={'id':'old','name':'Alt','category':'Bestehend','source':images.source_for_id('old')}
 with patch.object(images,'preview_source',return_value=(data,'image/png')):
  entry,_=images.import_record(record,None,root,root.parent/'cache')
 write(root,'catalog.json',images.build_catalog([entry]))
 write(root,'data/motifs-manifest.json',{'version':1,'generatedAt':'baseline','generator':images.GENERATOR,'motifs':[entry]})
 write(root,'data/motifs-baseline.json',{'version':1,'motifs':[{'id':'old','name':'Alt','category':'Bestehend'}]})
 write(root,'data/categories.json',{'version':1,'categories':[{'id':'legacy-fixed','key':'Bestehend','name':'Bestehend','folderId':None,'rootFolderId':'root','parentId':None}]})
 write(root,'motifs.sources.json',{'version':1,'deleteMissing':False,'roots':[{'folderId':'root','recursive':True,'includeRootImages':False,'excludeFolderNamesContaining':['LOGO','Schriften'],'excludeFolderIds':[]}],'imageMimeTypes':list(sync.FORMATS)})
 tree={'root':[folder('a','Bestehend'),folder('logos','LOGO'),folder('fonts','Schriften')],'a':[image('old','Alt.png',data)],'logos':[],'fonts':[]}
 return FakeDrive(tree,{'old':data})

class SyncChecks(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.temp.name)/'repo';self.api=fixture(self.root)
 def tearDown(self):self.temp.cleanup()
 def run_sync(self):return sync.synchronize(self.root,self.api,True)
 def test_inventory_reports_exclusions_but_never_downloads_or_writes(self):
  before=snapshot(self.root);self.api.tree['root'].append(folder('new','Leer'));self.api.tree['new']=[]
  report=sync.synchronize(self.root,self.api)
  self.assertEqual(snapshot(self.root),before);self.assertEqual(self.api.downloads,[])
  self.assertEqual(report['newCategories'],['drive-new']);self.assertEqual(len(report['rootFolders']),4)
  self.assertEqual(sum(f['excluded'] for f in report['rootFolders']),2)
  self.assertNotIn('logos',self.api.reads);self.assertNotIn('fonts',self.api.reads)
 def test_initial_verification_reuses_both_existing_webps_and_later_skips_downloads(self):
  before={p:p.read_bytes() for p in self.root.rglob('*.webp')}
  report=self.run_sync();self.assertEqual(report['verifiedExisting'],['old']);self.assertEqual(report['changedImages'],[])
  self.assertEqual(before,{p:p.read_bytes() for p in self.root.rglob('*.webp')});self.assertEqual(self.api.downloads,['old'])
  before=snapshot(self.root);self.api.downloads=[];report=self.run_sync()
  self.assertEqual(self.api.downloads,[]);self.assertEqual(report['unchangedImages'],['old']);self.assertEqual(report['changedFiles'],[]);self.assertEqual(snapshot(self.root),before)
 def test_new_nested_folder_and_alpha_image_keep_stable_ids_through_rename_and_move(self):
  self.run_sync();data=blob((0,77,180,0),secret=True)
  self.api.tree['a'].append(folder('nested','Neu'));self.api.tree['nested']=[image('new-image','Geschenk.png',data)];self.api.payloads['new-image']=data
  report=self.run_sync();self.assertEqual(report['newImages'],['new-image']);self.assertEqual(report['newCategories'],['drive-nested'])
  state=images.read_json(self.root/'data/categories.json');cat=next(c for c in state['categories'] if c['id']=='drive-nested');self.assertEqual(cat['parentId'],'legacy-fixed')
  entries=images.read_json(self.root/'data/motifs-manifest.json')['motifs'];new=next(e for e in entries if e['id']=='new-image')
  for meta in new['variants'].values():
   with Image.open(self.root/meta['path']) as im:
    self.assertEqual(im.getpixel((0,0))[3],0);self.assertNotIn('exif',im.info);self.assertNotIn('xmp',im.info);self.assertNotIn('icc_profile',im.info)
  self.api.tree['a']=[self.api.tree['a'][0]];self.api.tree['root'].append(folder('nested','Umbenannt'))
  self.api.downloads=[];report=self.run_sync();self.assertIn('drive-nested',report['renamedCategories']);self.assertIn('drive-nested',report['movedCategories'])
  self.assertEqual(self.api.downloads,[]);cat=next(c for c in images.read_json(self.root/'data/categories.json')['categories'] if c['id']=='drive-nested');self.assertIsNone(cat['parentId'])
  self.assertEqual(next(e for e in images.read_json(self.root/'catalog.json') if e['id']=='new-image')['categoryId'],'drive-nested')
 def test_actual_content_change_adds_only_changed_previews_and_retains_old_assets(self):
  self.run_sync();old=set(self.root.rglob('*.webp'));data=blob('blue');self.api.payloads['old']=data;self.api.tree['a']=[image('old','Alt.png',data)]
  report=self.run_sync();self.assertEqual(report['changedImages'],['old']);self.assertTrue(old.issubset(set(self.root.rglob('*.webp'))));self.assertEqual(len(list(self.root.rglob('*.webp'))),4)
 def test_missing_permissions_corrupt_images_and_decoder_errors_are_transactional(self):
  before=snapshot(self.root);self.api.tree['a']=sync.SyncError('Read denied')
  with self.assertRaises(sync.SyncError):self.run_sync()
  self.assertEqual(before,snapshot(self.root))
  self.api.tree['a']=[image('old','Alt.png',b'not an image')];self.api.payloads['old']=b'not an image'
  with self.assertRaises(sync.SyncError):self.run_sync()
  self.assertEqual(before,snapshot(self.root))
 def test_missing_images_and_categories_are_retained_and_excluded_ids_stay_excluded(self):
  self.run_sync();self.api.tree['root']=[folder('logos','Now innocent'),folder('fonts','Schriften')]
  self.api.tree['logos']=[image('bad','Do not import.png',blob())]
  report=self.run_sync();self.assertEqual(report['missingImagesRetained'],['old']);self.assertEqual(len(images.read_json(self.root/'catalog.json')),1)
  self.assertTrue(any(c['id']=='legacy-fixed' for c in images.read_json(self.root/'data/categories.json')['categories']));self.assertNotIn('bad',self.api.downloads)
 def test_empty_categories_and_duplicate_names_have_distinct_folder_identities(self):
  self.api.tree['root'] += [folder('empty-one','Leer'),folder('empty-two','Leer')];self.api.tree.update({'empty-one':[],'empty-two':[]})
  report=self.run_sync();self.assertEqual(set(report['newCategories']),{'drive-empty-one','drive-empty-two'});self.assertEqual(sync.validate_categories(self.root),3)
 def test_ambiguous_legacy_mapping_fails_closed(self):
  self.api.tree['root'].append(folder('b','Bestehend'));self.api.tree['b']=[];self.api.tree['a']=[]
  with self.assertRaises(sync.SyncError):self.run_sync()
 def test_secret_like_names_refuse_generated_output(self):
  before=snapshot(self.root);self.api.tree['root'].append(folder('bad','ghp_'+'A'*40));self.api.tree['bad']=[]
  with self.assertRaises(sync.SyncError):self.run_sync()
  self.assertEqual(before,snapshot(self.root))
 def test_unexpected_output_paths_and_non_image_formats_rejected(self):
  self.assertFalse(sync.allowed_path('original.png'));self.assertFalse(sync.allowed_path('assets/motifs/id/../../secret.webp'));self.assertFalse(sync.allowed_path('.github/workflows/injected.yml'))
  with self.assertRaises(sync.SyncError):sync.screen_source(blob(),'image/jpeg')
 def test_unsupported_animation_and_size_are_rejected(self):
  out=io.BytesIO();Image.new('RGB',(5,5),'red').save(out,format='GIF',save_all=True,append_images=[Image.new('RGB',(5,5),'blue')])
  with self.assertRaises(sync.SyncError):sync.screen_source(out.getvalue(),'image/gif')
  with patch.object(sync,'MAX_PIXELS',1):
   with self.assertRaises(sync.SyncError):sync.screen_source(blob(),'image/png')
 def test_eleven_simulated_root_folders_yield_nine_categories(self):
  for i in range(8):
   self.api.tree['root'].append(folder('more-'+str(i),'Motiv '+str(i)));self.api.tree['more-'+str(i)]=[]
  report=self.run_sync();self.assertEqual(len(report['rootFolders']),11)
  self.assertEqual(sum(f['excluded'] for f in report['rootFolders']),2)
  self.assertEqual(sync.validate_categories(self.root),9)
 def test_metadata_rename_skips_reencoding(self):
  self.run_sync();before=set(self.root.rglob('*.webp'));self.api.downloads=[]
  self.api.tree['a'][0]['name']='Neuer Name.png'
  report=self.run_sync();self.assertEqual(self.api.downloads,[]);self.assertEqual(set(self.root.rglob('*.webp')),before)
  self.assertEqual(report['metadataOnlyImages'],['old']);self.assertEqual(images.read_json(self.root/'catalog.json')[0]['name'],'Neuer Name')
 def test_late_corrupt_image_and_post_write_failure_leave_repository_unchanged(self):
  before=snapshot(self.root);self.api.tree['a'].append(image('broken','Broken.png',b'bad'));self.api.payloads['broken']=b'bad'
  with self.assertRaises(sync.SyncError):self.run_sync()
  self.assertEqual(before,snapshot(self.root))
  self.api.tree['a']=self.api.tree['a'][:1]
  original=images.validate;calls=[]
  def validate(root,*args):
   calls.append(1)
   if len(calls)>1:raise ValueError('post-write fault')
   return original(root,*args)
  with patch.object(images,'validate',side_effect=validate):
   with self.assertRaises(sync.SyncError):self.run_sync()
  self.assertEqual(before,snapshot(self.root))
 def test_icc_alpha_and_exif_orientation_are_normalized_without_private_metadata(self):
  profile=sync.ImageCms.ImageCmsProfile(sync.ImageCms.createProfile('sRGB')).tobytes()
  original=Image.new('RGBA',(20,10),(77,88,99,42));out=io.BytesIO();original.save(out,format='PNG',icc_profile=profile)
  normalized,fmt=sync.screen_source(out.getvalue(),'image/png')
  self.assertEqual(fmt,'PNG');self.assertEqual(normalized.getpixel((0,0))[3],42);self.assertEqual(normalized.info,{})
  out=io.BytesIO();exif=Image.Exif();exif[274]=6;Image.new('RGB',(80,40),'red').save(out,format='JPEG',exif=exif)
  normalized,_=sync.screen_source(out.getvalue(),'image/jpeg');self.assertEqual(normalized.size,(40,80));self.assertEqual(normalized.info,{})
 def test_invalid_category_cycles_are_rejected(self):
  self.run_sync();data=images.read_json(self.root/'data/categories.json');data['categories'][0]['parentId']='legacy-fixed'
  write(self.root,'data/categories.json',data)
  with self.assertRaises(sync.SyncError):sync.validate_categories(self.root)
 def test_pending_record_merge_keeps_both_sides_and_rejects_conflicts(self):
  base=[{'id':'a','name':'a'}];current=base+[{'id':'main-new'}];pending=base+[{'id':'pending-new'}]
  self.assertEqual({e['id'] for e in guard.three_way(base,current,pending)},{'a','main-new','pending-new'})
  with self.assertRaises(sync.SyncError):guard.three_way(base,[{'id':'a','name':'main'}],[{'id':'a','name':'pending'}])
  with self.assertRaises(sync.SyncError):guard.three_way(base,base,[])

class PendingSeedChecks(unittest.TestCase):
 def test_pending_data_is_merged_without_executing_its_code_and_unknown_paths_are_refused(self):
  with tempfile.TemporaryDirectory() as temp:
   root=pathlib.Path(temp)/'repo';api=fixture(root)
   def run(*args):return subprocess.check_output(['git',*args],cwd=root,stderr=subprocess.DEVNULL).decode().strip()
   run('init','-b','main');run('config','user.name','Offline');run('config','user.email','offline@example.invalid')
   run('add','.');run('commit','-qm','baseline');base=run('rev-parse','HEAD')
   run('switch','-c','bot/drive-motifs-sync');pending_api=copy.deepcopy(api);data=blob('green')
   pending_api.tree['a'].append(image('pending-new','Pending.png',data));pending_api.payloads['pending-new']=data
   sync.synchronize(root,pending_api,True);run('add','.');run('commit','-qm','pending');pending=run('rev-parse','HEAD')
   run('switch','main');current_api=copy.deepcopy(api);data=blob('blue')
   current_api.tree['a'].append(image('main-new','Main.png',data));current_api.payloads['main-new']=data
   sync.synchronize(root,current_api,True);run('add','.');run('commit','-qm','current')
   original_git,original_run=guard.git,subprocess.run
   def git(root,*args,**kwargs):
    if args[0]=='fetch':(root/'.git/FETCH_HEAD').write_text(pending+'\n');return ''
    return original_git(root,*args,**kwargs)
   def command(args,*a,**kwargs):
    if args[:3]==['gh','pr','list']:return subprocess.CompletedProcess(args,0,json.dumps([{'number':1,'isCrossRepository':False,'headRefOid':pending}]).encode(),b'')
    return original_run(args,*a,**kwargs)
   with patch.object(guard,'git',side_effect=git),patch.object(guard.subprocess,'run',side_effect=command):
    self.assertTrue(guard.seed_pending(root))
   self.assertEqual({d['id'] for d in images.read_json(root/'catalog.json')},{'old','main-new','pending-new'})
   self.assertTrue(all(sync.allowed_path(p) for p in guard.changed_paths(root)))
   run('reset','--hard','HEAD');run('clean','-fd');run('switch','bot/drive-motifs-sync')
   (root/'.github/workflows').mkdir(parents=True);(root/'.github/workflows/attack.yml').write_text('not allowed')
   run('add','.');run('commit','-qm','unexpected-code');pending=run('rev-parse','HEAD');run('switch','main');before=snapshot(root)
   with patch.object(guard,'git',side_effect=git),patch.object(guard.subprocess,'run',side_effect=command):
    with self.assertRaises(sync.SyncError):guard.seed_pending(root)
   self.assertEqual(before,snapshot(root))

 def test_fork_prs_and_changed_remote_heads_do_not_seed_data(self):
  with tempfile.TemporaryDirectory() as temp:
   root=pathlib.Path(temp)/'repo';fixture(root);before=snapshot(root)
   fork=subprocess.CompletedProcess([],0,json.dumps([{'number':1,'isCrossRepository':True,'headRefOid':'a'*40}]).encode(),b'')
   with patch.object(guard.subprocess,'run',return_value=fork),patch.object(guard,'git') as git:
    self.assertFalse(guard.seed_pending(root));git.assert_not_called()
   own=subprocess.CompletedProcess([],0,json.dumps([{'number':1,'isCrossRepository':False,'headRefOid':'a'*40}]).encode(),b'')
   with patch.object(guard.subprocess,'run',return_value=own),patch.object(guard,'git',side_effect=['','b'*40]):
    with self.assertRaises(sync.SyncError):guard.seed_pending(root)
   self.assertEqual(before,snapshot(root))

class APIAndWorkflowChecks(unittest.TestCase):
 def test_get_only_pagination_and_no_token_forwarding(self):
  class Response:
   def __init__(self,data):self.body=json.dumps(data).encode()
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self,n):return self.body[:n]
  class Opener:
   def __init__(self):self.calls=[];self.responses=iter([{'files':[{'id':'one'}],'nextPageToken':'two'},{'files':[]}])
   def open(self,request,timeout):self.calls.append(request);return Response(next(self.responses))
  opener=Opener();api=sync.DriveAPI('OFFLINE-ONLY',opener);self.assertEqual(list(api.children('root')),[{'id':'one'}])
  self.assertTrue(all(r.get_method()=='GET' and 'OFFLINE-ONLY' not in r.full_url for r in opener.calls))
  self.assertIn('pageToken=two',opener.calls[1].full_url)
  with self.assertRaises(sync.SyncError):sync.NoRedirect().redirect_request()
 def test_download_size_md5_and_http_error_redaction(self):
  class Response:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self,n):return b'wrong content'
  class Opener:
   def open(self,*args,**kwargs):return Response()
  api=sync.DriveAPI('NOT-A-REAL-TOKEN',Opener())
  with self.assertRaises(sync.SyncError):api.download(image('id','Name.png',blob()))
  with self.assertRaises(sync.SyncError):api.download({'id':'id','size':sync.MAX_BYTES+1})
  import urllib.error
  class ErrorOpener:
   def open(self,*args,**kwargs):raise urllib.error.HTTPError('https://source?token=DO_NOT_LOG',403,'DO_NOT_LOG',{},None)
  with self.assertRaises(sync.SyncError) as error:sync.DriveAPI('DO_NOT_LOG',ErrorOpener()).root('root')
  self.assertNotIn('DO_NOT_LOG',str(error.exception));self.assertIn('403',str(error.exception))
 def test_incomplete_or_repeating_api_pages_are_not_successful(self):
  class Response:
   def __init__(self,d):self.data=json.dumps(d).encode()
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self,n):return self.data[:n]
  class Opener:
   def __init__(self,d):self.data=d
   def open(self,*args,**kwargs):return Response(self.data)
  for data in [{'files':[],'incompleteSearch':True},{'files':[],'nextPageToken':'same'}]:
   with self.assertRaises(sync.SyncError):list(sync.DriveAPI('OFFLINE-ONLY',Opener(data)).children('root'))
 def test_workflow_has_no_timer_deploy_or_artifacts_and_scopes_are_separated(self):
  import yaml
  w=yaml.load((ROOT/'.github/workflows/drive-motifs-sync.yml').read_text(),Loader=yaml.BaseLoader)
  self.assertEqual(set(w['on']),{'workflow_dispatch'});self.assertEqual(w['permissions'],{})
  self.assertEqual(w['jobs']['inventory']['permissions'],{'contents':'read','id-token':'write'})
  for job in w['jobs'].values():
   self.assertIn("github.ref == 'refs/heads/main'",job['if'])
   for step in job['steps']:
    self.assertNotIn('upload-artifact',step.get('uses',''));self.assertNotIn('deploy',step.get('uses',''))
    if 'uses' in step:self.assertRegex(step['uses'],r'@[a-f0-9]{40}$')
  pr=w['jobs']['prepare']['steps'][-1];self.assertEqual(pr['with']['base'],'main');self.assertEqual(pr['with']['branch'],'bot/drive-motifs-sync');self.assertEqual(pr['with']['draft'],'always-true')

if __name__=='__main__':
 with patch.object(socket,'create_connection',side_effect=AssertionError('Offline tests must never use network')):unittest.main()
