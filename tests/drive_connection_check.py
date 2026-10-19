"""Offline-only contract checks: simulated HTTP, never a real token or API request."""
import contextlib,importlib.util,io,json,pathlib,socket,unittest,urllib.error
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('connection',ROOT/'tools/check_drive_connection.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
FAKE='OFFLINE_SENTINEL_NOT_A_REAL_CREDENTIAL'
class Response:
 def __init__(self,data):self.body=json.dumps(data).encode()
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def read(self,n):return self.body[:n]
class FakeOpener:
 def __init__(self,payloads):self.payloads=iter(payloads);self.requests=[]
 def open(self,request,timeout):
  self.requests.append(request)
  data=next(self.payloads)
  if isinstance(data,Exception):raise data
  return Response(data)
class OfflineChecks(unittest.TestCase):
 def test_config_unique_existing_root(self):
  self.assertEqual(m.configured_root(ROOT/'motifs.sources.json'),'12OdcNV5wB5S1H471D0F8th9EJ2LFrJ6G')
 def test_all_folder_levels_and_pagination_get_only(self):
  opener=FakeOpener([
   {'id':'root','name':'TimberArt_Designs','mimeType':m.FOLDER,'trashed':False},
   {'files':[{'id':'child','mimeType':m.FOLDER}],'nextPageToken':'next'},
   {'files':[{'id':'second','mimeType':m.FOLDER}]},
   {'files':[{'id':'grandchild','mimeType':m.FOLDER}]},
   {'files':[]}, {'files':[]},
  ])
  result=m.check_folders(m.DriveMetadata(FAKE,opener),'root')
  self.assertEqual(result,{'direct_subfolders':2,'all_subfolders':3,'max_depth':2})
  self.assertEqual(len(opener.requests),6)
  for request in opener.requests:
   self.assertEqual(request.get_method(),'GET')
   self.assertEqual(request.get_header('Authorization'),'Bearer '+FAKE)
   self.assertTrue(request.full_url.startswith('https://www.googleapis.com/drive/v3/files'))
   self.assertNotIn(FAKE,request.full_url);self.assertNotIn('alt=',request.full_url)
  self.assertIn('pageToken=next',opener.requests[2].full_url)
 def test_http_errors_do_not_disclose_payload_or_token(self):
  for code in [401,403,404,429,503]:
   opener=FakeOpener([urllib.error.HTTPError('https://source?secret='+FAKE,code,FAKE,{},io.BytesIO(FAKE.encode()))])
   with self.assertRaises(m.CheckError) as error:m.DriveMetadata(FAKE,opener).get('files/root',{'fields':'id'})
   self.assertIn(str(code),str(error.exception));self.assertNotIn(FAKE,str(error.exception))
 def test_media_paths_and_redirects_blocked(self):
  opener=FakeOpener([]);api=m.DriveMetadata(FAKE,opener)
  for path,params in [('files/root',{'alt':'media'}),('https://attacker.invalid',{}),('files/../other',{})]:
   with self.assertRaises(m.CheckError):api.get(path,params)
  self.assertEqual(opener.requests,[])
  with self.assertRaises(m.CheckError):m.NoRedirect().redirect_request(None,None,302,'Found',{},'https://accounts.google.com/')
 def test_bad_tree_never_declares_success(self):
  root={'id':'root','name':'TimberArt_Designs','mimeType':m.FOLDER,'trashed':False}
  for page in [{'files':[]},{'files':[],'incompleteSearch':True},{'files':[{'id':'root','mimeType':m.FOLDER}]},{'files':[{'id':'image','mimeType':'image/png'}]}]:
   with self.assertRaises(m.CheckError):m.check_folders(m.DriveMetadata(FAKE,FakeOpener([root,page])),'root')
  bad=dict(root,name='Wrong root')
  with self.assertRaises(m.CheckError):m.check_folders(m.DriveMetadata(FAKE,FakeOpener([bad])),'root')
 def test_main_logs_only_safe_failure(self):
  stdout,stderr=io.StringIO(),io.StringIO()
  with patch.object(m,'DriveMetadata',side_effect=RuntimeError(FAKE)),contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
   self.assertEqual(m.main(),1)
  self.assertNotIn(FAKE,stdout.getvalue()+stderr.getvalue());self.assertNotIn('PASS',stdout.getvalue())

if __name__=='__main__':
 # A real network connection during these checks is an immediate test failure.
 with patch.object(socket,'create_connection',side_effect=AssertionError('Network prohibited in offline checks')):
  unittest.main()
