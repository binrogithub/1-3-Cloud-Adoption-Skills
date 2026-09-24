#!/usr/bin/env python3
import json, os, subprocess, tempfile, threading, unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/autoops-e2e-preflight.sh'
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers(); self.wfile.write(b'{}')
 def log_message(self,*_): pass
class TestPreflight(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler); cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True); cls.thread.start()
 @classmethod
 def tearDownClass(cls): cls.server.shutdown(); cls.thread.join()
 def test_verifies_all_required_endpoints(self):
  env=os.environ|{'RUNDECK_BASE_URL':f'http://127.0.0.1:{self.server.server_port}','RUNDECK_API_TOKEN':'test','RUNDECK_PROJECT':'autoops','RUNDECK_HOST_BASIC_CHECK_JOB_ID':'job-read','RUNDECK_ANSIBLE_ENSURE_SERVICE_JOB_ID':'job-write'}
  result=subprocess.run([str(SCRIPT)],text=True,capture_output=True,env=env)
  self.assertEqual(result.returncode,0,result.stderr); self.assertIn('Ansible service Job verified',result.stdout)
 def test_required_datasource_missing_blocks(self):
  with tempfile.TemporaryDirectory() as directory:
   env=os.environ|{'RUNDECK_BASE_URL':f'http://127.0.0.1:{self.server.server_port}','RUNDECK_API_TOKEN':'test','RUNDECK_PROJECT':'autoops','RUNDECK_HOST_BASIC_CHECK_JOB_ID':'job-read','RUNDECK_ANSIBLE_ENSURE_SERVICE_JOB_ID':'job-write','AUTOOPS_PREFLIGHT_REQUIRED_SOURCES':'loki','JIUWENSWARM_AUTOOPS_CONFIG_DIR':directory}
   result=subprocess.run([str(SCRIPT)],text=True,capture_output=True,env=env)
   self.assertEqual(result.returncode,3,result.stderr)
   self.assertEqual(json.loads(result.stdout)['status'],'BLOCKED')
 def test_optional_datasource_missing_degrades_without_blocking(self):
  with tempfile.TemporaryDirectory() as directory:
   env=os.environ|{'RUNDECK_BASE_URL':f'http://127.0.0.1:{self.server.server_port}','RUNDECK_API_TOKEN':'test','RUNDECK_PROJECT':'autoops','RUNDECK_HOST_BASIC_CHECK_JOB_ID':'job-read','RUNDECK_ANSIBLE_ENSURE_SERVICE_JOB_ID':'job-write','AUTOOPS_PREFLIGHT_OPTIONAL_SOURCES':'opensearch','JIUWENSWARM_AUTOOPS_CONFIG_DIR':directory}
   result=subprocess.run([str(SCRIPT)],text=True,capture_output=True,env=env)
   self.assertEqual(result.returncode,0,result.stderr)
   self.assertEqual(json.loads(result.stdout)['status'],'DEGRADED')
if __name__=='__main__': unittest.main()
