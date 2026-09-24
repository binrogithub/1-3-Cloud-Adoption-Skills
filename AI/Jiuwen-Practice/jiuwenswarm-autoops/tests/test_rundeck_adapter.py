#!/usr/bin/env python3
import json, os, sqlite3, subprocess, sys, tempfile, threading, unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; SCRIPT=ROOT/'scripts/runbook-execute.py'
RECONCILE=ROOT/'scripts/autoops-task-reconcile.py'
class Handler(BaseHTTPRequestHandler):
    starts=0
    detail_status='SUCCEEDED'
    invalid_start_response=False
    fail_output=False
    output_text='check passed token=hidden'
    def do_POST(self):
        type(self).starts+=1; self.send_response(200); self.end_headers()
        self.wfile.write(b'{}' if type(self).invalid_start_response else b'{"id":42}')
    def do_GET(self):
        if self.path.endswith('/output') and type(self).fail_output:
            self.send_response(500); self.end_headers(); return
        self.send_response(200); self.end_headers()
        body=json.dumps({'entries':[{'log':type(self).output_text}]}).encode() if self.path.endswith('/output') else json.dumps({'id':42,'status':type(self).detail_status}).encode()
        self.wfile.write(body)
    def log_message(self,*_): pass
class TestRundeck(unittest.TestCase):
  @classmethod
  def setUpClass(cls):
    cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler); cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True); cls.thread.start()
  @classmethod
  def tearDownClass(cls): cls.server.shutdown(); cls.thread.join()
  def setUp(self):
    Handler.detail_status='SUCCEEDED'
    Handler.invalid_start_response=False
    Handler.fail_output=False
    Handler.output_text='check passed token=hidden'
    self.tmp=tempfile.TemporaryDirectory(); p=Path(self.tmp.name); self.registry=p/'jobs.json'; self.db=p/'runs.db'; self.state_db=p/'state.db'
    self.registry.write_text(json.dumps({'jobs':[{'name':'host-basic-check','id':'job-1','options':{'target':'^[A-Za-z0-9.-]+$'}}]}))
    self.registry.chmod(0o600)
    self.env=os.environ|{'RUNDECK_BASE_URL':f'http://127.0.0.1:{self.server.server_port}','RUNDECK_API_TOKEN':'test','RUNDECK_JOB_REGISTRY':str(self.registry),'AUTOOPS_EXECUTION_DB':str(self.db),'AUTOOPS_STATE_DB':str(self.state_db),'AUTOOPS_AUTHENTICATED_ROLE':'runbook-operator','RUNDECK_POLL_MAX_SECONDS':'0'}
  def tearDown(self): self.tmp.cleanup()
  def execute(self,*args): return subprocess.run([str(SCRIPT),'--task-id','task-1','--idempotency-key','key-1','--job','host-basic-check','--target','test-host-01',*args],text=True,capture_output=True,env=self.env)
  def test_starts_once_and_reuses_execution(self):
    before=Handler.starts; first=self.execute(); second=self.execute()
    self.assertEqual(first.returncode,0,first.stderr); self.assertEqual(second.returncode,0,second.stderr)
    payload=json.loads(second.stdout); self.assertEqual(Handler.starts,before+1); self.assertEqual(payload['external_execution_id'],'42'); self.assertEqual(payload['output_summary'],['check passed token=[REDACTED]'])

  def test_ansible_recap_distinguishes_no_change(self):
    Handler.output_text='PLAY RECAP test-host-01 : ok=1 changed=0 unreachable=0 failed=0'
    result=self.execute()
    self.assertEqual(result.returncode,0,result.stderr)
    self.assertEqual(json.loads(result.stdout)['ansible_recap'],{'result':'NO_CHANGE','changed':0,'failed':0})

  def test_ansible_failure_recap_is_not_no_change(self):
    Handler.output_text='PLAY RECAP test-host-01 : ok=0 changed=0 unreachable=0 failed=1'
    result=self.execute()
    self.assertEqual(result.returncode,0,result.stderr)
    self.assertEqual(json.loads(result.stdout)['ansible_recap'],{'result':'FAILED','changed':0,'failed':1})
  def test_rejects_unpublished_job(self):
    result=subprocess.run([str(SCRIPT),'--task-id','t','--idempotency-key','x','--job','other','--target','test-host-01'],text=True,capture_output=True,env=self.env)
    self.assertEqual(result.returncode,2); self.assertEqual(json.loads(result.stdout)['status'],'JOB_NOT_ALLOWED')
  def test_rejects_untrusted_role(self):
    env=self.env|{'AUTOOPS_AUTHENTICATED_ROLE':'ops-leader'}; result=subprocess.run([str(SCRIPT),'--task-id','t','--idempotency-key','x','--job','host-basic-check','--target','test-host-01'],text=True,capture_output=True,env=env)
    self.assertEqual(result.returncode,2); self.assertEqual(json.loads(result.stdout)['status'],'PERMISSION_DENIED')
  def test_unknown_intent_is_not_resubmitted(self):
    conn=sqlite3.connect(self.db); conn.execute('CREATE TABLE executions (key TEXT PRIMARY KEY, task_id TEXT, job TEXT, target TEXT, execution_id TEXT, status TEXT, created_at INTEGER)'); conn.execute('INSERT INTO executions VALUES (?,?,?,?,?,?,?)',('key-1','task-1','host-basic-check','test-host-01',None,'INTENT_RECORDED',0)); conn.commit(); conn.close()
    before=Handler.starts; result=self.execute(); self.assertEqual(result.returncode,0); self.assertEqual(json.loads(result.stdout)['status'],'UNKNOWN'); self.assertEqual(Handler.starts,before)
  def test_lost_submit_response_is_unknown_and_not_resubmitted(self):
    Handler.invalid_start_response=True
    sys_path = str(ROOT / 'scripts')
    sys.path.insert(0, sys_path)
    from autoops_task_store import TaskStore
    ledger = TaskStore(Path(self.env['AUTOOPS_STATE_DB']))
    ledger.upsert('task-1', 'key-1', {'operation_id': 'key-1'}, status='RUNNING')
    ledger.close()
    before=Handler.starts
    first=self.execute(); second=self.execute()
    self.assertEqual(first.returncode,1)
    self.assertEqual(json.loads(first.stdout)['status'],'UNKNOWN')
    self.assertEqual(second.returncode,0)
    self.assertEqual(json.loads(second.stdout)['status'],'UNKNOWN')
    self.assertEqual(Handler.starts,before+1)
    ledger = TaskStore(Path(self.env['AUTOOPS_STATE_DB']))
    self.assertEqual(ledger.get('task-1')['status'], 'RECONCILING')
    self.assertEqual(ledger.events('task-1')[-1]['event_type'], 'external.execution_unknown')
    self.assertEqual(ledger.events('task-1')[-1]['payload']['reconcile_policy'], 'query_existing_execution_only')
    ledger.close()

  def test_lost_output_response_reconciles_original_execution_after_cancel(self):
    Handler.fail_output=True
    sys.path.insert(0, str(ROOT / 'scripts'))
    from autoops_task_store import TaskStore
    ledger = TaskStore(Path(self.env['AUTOOPS_STATE_DB']))
    ledger.upsert('task-1', 'key-1', {'operation_id': 'key-1'}, status='RUNNING')
    ledger.close()
    first=self.execute()
    self.assertEqual(first.returncode,1)
    self.assertEqual(json.loads(first.stdout)['status'],'UNKNOWN')
    from autoops_task_store import TaskStore
    ledger = TaskStore(Path(self.env['AUTOOPS_STATE_DB']))
    self.assertEqual(ledger.get('task-1')['status'], 'RECONCILING')
    ledger.request_cancel('task-1', 'operator stopped while response was lost')
    ledger.close()
    Handler.fail_output=False
    before=Handler.starts
    result=subprocess.run([str(RECONCILE),'--task-id','task-1','--state-db',self.env['AUTOOPS_STATE_DB'],
                           '--execution-db',self.env['AUTOOPS_EXECUTION_DB']],text=True,capture_output=True,env=self.env)
    payload=json.loads(result.stdout)
    self.assertEqual(result.returncode,0,result.stderr)
    self.assertEqual(payload['status'],'SUCCEEDED')
    self.assertEqual(Handler.starts,before)
    ledger = TaskStore(Path(self.env['AUTOOPS_STATE_DB']))
    self.assertEqual(ledger.get('task-1')['status'],'SUCCEEDED')
    self.assertEqual(ledger.events('task-1')[-1]['event_type'],'external.execution_reconciled')
    self.assertEqual(len([event for event in ledger.events('task-1')
                          if event['event_type'] == 'task.cancel_requested']), 1)
    ledger.close()
  def test_lowercase_running_is_retryable(self):
    Handler.detail_status='running'; result=self.execute(); payload=json.loads(result.stdout)
    self.assertEqual(result.returncode,0,result.stderr); self.assertEqual(payload['status'],'running'); self.assertTrue(payload['retryable'])
  def test_unknown_rundeck_status_enters_reconciliation(self):
    Handler.detail_status='UNKNOWN'
    sys.path.insert(0, str(ROOT / 'scripts'))
    from autoops_task_store import TaskStore
    ledger = TaskStore(Path(self.env['AUTOOPS_STATE_DB']))
    ledger.upsert('task-1', 'key-1', {'operation_id': 'key-1'}, status='RUNNING')
    ledger.close()
    result=self.execute(); payload=json.loads(result.stdout)
    self.assertEqual(result.returncode,1)
    self.assertEqual(payload['status'],'UNKNOWN')
    self.assertEqual(payload['error_code'],'RESULT_UNKNOWN')
    ledger = TaskStore(Path(self.env['AUTOOPS_STATE_DB']))
    self.assertEqual(ledger.get('task-1')['status'], 'RECONCILING')
    ledger.close()
  def test_existing_execution_reports_reconciliation_while_running(self):
    Handler.detail_status='running'
    first=self.execute(); self.assertEqual(first.returncode,0,first.stderr)
    second=self.execute(); payload=json.loads(second.stdout)
    self.assertEqual(second.returncode,0,second.stderr)
    self.assertTrue(payload['reconciliation'])
    self.assertTrue(payload['retryable'])

  def test_reconcile_command_queries_original_execution_and_settles_task(self):
    Handler.detail_status='SUCCEEDED'
    sys.path.insert(0, str(ROOT / 'scripts'))
    from autoops_task_store import TaskStore
    ledger = TaskStore(Path(self.env['AUTOOPS_STATE_DB']))
    ledger.upsert('task-1', 'key-1', {'operation_id': 'key-1'}, status='RECONCILING')
    ledger.event('task-1', 'external.execution_unknown', {
      'job': 'host-basic-check', 'target': 'test-host-01',
      'operation_id': 'key-1', 'reconcile_policy': 'query_existing_execution_only',
    })
    ledger.close()
    run = self.execute()
    self.assertEqual(run.returncode,0,run.stderr)
    before=Handler.starts
    result=subprocess.run([str(RECONCILE),'--task-id','task-1','--state-db',self.env['AUTOOPS_STATE_DB'],
                           '--execution-db',self.env['AUTOOPS_EXECUTION_DB']],text=True,capture_output=True,env=self.env)
    payload=json.loads(result.stdout)
    self.assertEqual(result.returncode,0,result.stderr)
    self.assertEqual(payload['status'],'SUCCEEDED')
    self.assertEqual(Handler.starts,before)
    ledger = TaskStore(Path(self.env['AUTOOPS_STATE_DB']))
    self.assertEqual(ledger.get('task-1')['status'],'SUCCEEDED')
    self.assertEqual(ledger.events('task-1')[-1]['event_type'],'external.execution_reconciled')
    ledger.close()
  def test_rejects_same_idempotency_key_with_different_parameters(self):
    first=self.execute(); self.assertEqual(first.returncode,0,first.stderr)
    result=subprocess.run([str(SCRIPT),'--task-id','task-2','--idempotency-key','key-1','--job','host-basic-check','--target','other-host'],text=True,capture_output=True,env=self.env)
    self.assertEqual(result.returncode,2)
    self.assertEqual(json.loads(result.stdout)['status'],'IDEMPOTENCY_CONFLICT')
if __name__=='__main__': unittest.main()
