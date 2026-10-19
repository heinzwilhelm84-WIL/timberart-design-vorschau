"""Offline contract checks for safe, repeatable image imports and folder discovery."""
import copy, importlib.util, io, json, pathlib, tempfile, unittest
from unittest.mock import patch
from PIL import Image
spec=importlib.util.spec_from_file_location('sync_motifs',pathlib.Path(__file__).resolve().parents[1]/'tools/sync_motifs.py')
sync=importlib.util.module_from_spec(spec);spec.loader.exec_module(sync)

class ImportChecks(unittest.TestCase):
 def test_alpha_and_bilevel_preserved_without_upscaling(self):
  for mode in ['RGBA','1']:
   image=Image.new(mode,(120,80),(12,55,77,0) if mode=='RGBA' else 1)
   for edge in [60,1600]:
    payload,meta=sync.make_variant(image,edge)
    reference=image.copy();reference.thumbnail((edge,edge),Image.Resampling.LANCZOS)
    with Image.open(io.BytesIO(payload)) as result:
     self.assertEqual(result.convert('RGBA').tobytes(),reference.convert('RGBA').tobytes())
     self.assertLessEqual(max(result.size),min(edge,120))
 def test_incremental_reuse_and_repair_corruption(self):
  with tempfile.TemporaryDirectory() as folder:
   root=pathlib.Path(folder)/'repo';cache=pathlib.Path(folder)/'cache'
   source=Image.new('RGB',(800,400),'white');data=io.BytesIO();source.save(data,format='PNG')
   record={'id':'stable-id','name':'Motiv','category':'Tiere','source':sync.source_for_id('stable-id')}
   with patch.object(sync,'preview_source',return_value=(data.getvalue(),'image/png')) as request:
    entry,action=sync.import_record(record,None,root,cache)
    self.assertEqual(action,'generated');self.assertEqual(request.call_count,1)
    before={p:p.read_bytes() for p in root.rglob('*.webp')}
    repeated,action=sync.import_record(record,entry,root,cache,compatible=True)
    self.assertEqual(action,'unchanged');self.assertEqual(request.call_count,1)
    self.assertEqual(entry,repeated);self.assertEqual(before,{p:p.read_bytes() for p in root.rglob('*.webp')})
    # A corrupted existing asset is rejected, never silently reused.
    next(iter(before)).write_bytes(b'corrupt')
    with self.assertRaisesRegex(ValueError,'collision'):
     sync.import_record(record,entry,root,cache,compatible=True)
 def test_recursive_folders_exclusions_and_conflicting_ids(self):
  tree={'root':[{'id':'cat','name':'Tiere','mimeType':'application/vnd.google-apps.folder'}, {'id':'excluded','name':'LOGO','mimeType':'application/vnd.google-apps.folder'}],
        'cat':[{'id':'old-id','name':'Motiv.png','mimeType':'image/png'}, {'id':'nested','name':'Neu','mimeType':'application/vnd.google-apps.folder'}],
        'nested':[{'id':'new-id','name':'Neu.jpg','mimeType':'image/jpeg'}]}
  class Reader:
   def list_children(self,folder):return tree[folder]
  config={'version':1,'deleteMissing':False,'roots':[{'folderId':'root','recursive':True,'excludeFolderNamesContaining':['LOGO']}],'imageMimeTypes':['image/png','image/jpeg']}
  records=sync.discover_sources(config,Reader());self.assertEqual({r['id'] for r in records},{'old-id','new-id'})
  self.assertTrue(all(r['category']=='Tiere' for r in records))
  self.assertEqual(records[1]['source']['folderIds'],['cat','nested'])
  config['roots'].append({'folderId':'root','category':'Andere','excludeFolderNamesContaining':['LOGO']})
  with self.assertRaisesRegex(ValueError,'conflicting'):sync.discover_sources(config,Reader())
 def test_failed_batch_keeps_catalog_and_manifest(self):
  with tempfile.TemporaryDirectory() as folder:
   root=pathlib.Path(folder)/'repo';root.mkdir();cache=pathlib.Path(folder)/'cache'
   (root/'catalog.json').write_text(json.dumps([{'id':'old-id','name':'Alt','category':'Tiere'}]))
   before=(root/'catalog.json').read_bytes()
   args=type('Args',(),dict(repo=root,validate=False,apply=True,discover=False,refresh=False,cache=cache,workers=1))()
   with patch.object(sync,'import_record',side_effect=RuntimeError('Unavailable')):
    self.assertEqual(sync.run(args),1)
   self.assertEqual((root/'catalog.json').read_bytes(),before)
   self.assertFalse((root/'data/motifs-manifest.json').exists())
 def test_default_dry_run_retains_missing_and_never_imports(self):
  with tempfile.TemporaryDirectory() as folder:
   root=pathlib.Path(folder);(root/'data').mkdir()
   catalog=[{'id':'old-id','name':'Alt','category':'Tiere'}]
   (root/'catalog.json').write_text(json.dumps(catalog))
   (root/'data/motifs-manifest.json').write_text(json.dumps({'motifs':[dict(catalog[0],source=sync.source_for_id('old-id'))]}))
   before={p:p.read_bytes() for p in root.rglob('*') if p.is_file()}
   args=type('Args',(),dict(repo=root,validate=False,apply=False,discover=True,refresh=False,config=pathlib.Path('sources.json')))()
   with patch.object(sync,'DriveReader'),patch.object(sync,'discover_sources',return_value=[]),patch.object(sync,'import_record') as importer:
    self.assertEqual(sync.run(args),0);importer.assert_not_called()
   self.assertEqual(before,{p:p.read_bytes() for p in root.rglob('*') if p.is_file()})
 def test_drive_pagination_get_only_and_safe_errors(self):
  pages=[json.dumps({'files':[{'id':'one'}],'nextPageToken':'next'}).encode(),json.dumps({'files':[{'id':'two'}]}).encode()]
  with patch.object(sync,'http_get',side_effect=[(p,'application/json') for p in pages]) as get:
   result=list(sync.DriveReader(key='test-key').list_children('root'))
   self.assertEqual(result,[{'id':'one'},{'id':'two'}]);self.assertIn('pageToken=next',get.call_args_list[1].args[0])
  with patch.object(sync.urllib.request,'urlopen',side_effect=sync.urllib.error.HTTPError('https://source?key=SECRET',403,'SECRET',{},None)):
   with self.assertRaises(RuntimeError) as error:sync.http_get('https://source?key=SECRET')
   self.assertNotIn('SECRET',str(error.exception));self.assertIn('403',str(error.exception))
 def test_http_get_decompresses_and_rejects_large_responses(self):
  class Response:
   headers={'Content-Type':'application/json','Content-Encoding':'gzip'}
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self,maximum):return sync.gzip.compress(b'{"files":[]}')[:maximum]
  with patch.object(sync.urllib.request,'urlopen',return_value=Response()) as request:
   body,mime=sync.http_get('https://source')
   self.assertEqual(json.loads(body),{'files':[]});self.assertEqual(mime,'application/json')
   self.assertEqual(request.call_args.args[0].get_method(),'GET')
  class Large(Response):
   headers={'Content-Type':'image/png'}
   def read(self,maximum):return b'x'*maximum
  with patch.object(sync.urllib.request,'urlopen',return_value=Large()):
   with self.assertRaisesRegex(ValueError,'limit'):sync.http_get('https://source',maximum=100)
 def test_path_traversal_rejected(self):
  with self.assertRaises(ValueError):sync.asset_path(pathlib.Path('/tmp/repo'),'assets/motifs/../../secret')
  with self.assertRaises(ValueError):sync.source_for_id('../secret')

if __name__=='__main__':unittest.main()
