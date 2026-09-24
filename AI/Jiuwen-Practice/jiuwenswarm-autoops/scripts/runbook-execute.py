#!/usr/bin/env python3
"""Execute only an allowlisted Rundeck job and persist intent before submission."""
import argparse, hashlib, json, os, re, sqlite3, sys, time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DB = Path(os.environ.get('AUTOOPS_EXECUTION_DB', ROOT / '.runtime/executions.sqlite3'))

from autoops_rundeck_config import job_registry, load_rundeck_environment


def mark_reconciling(task_id, job, target, idempotency_key, execution_id=None, error=None):
    """Attach an unknown external outcome to the durable AutoOps task ledger."""
    try:
        from autoops_task_store import TaskStore
        store = TaskStore()
        try:
            if store.get(task_id) is not None:
                store.set_status(task_id, 'RECONCILING')
                store.event(task_id, 'external.execution_unknown', {
                    'job': job,
                    'target': target,
                    'operation_id': idempotency_key,
                    'external_execution_id': execution_id,
                    'error_code': 'RESULT_UNKNOWN',
                    'error': str(error) if error else None,
                    'reconcile_policy': 'query_existing_execution_only',
                })
        finally:
            store.close()
    except Exception:
        # The adapter must still return the safety-preserving UNKNOWN result;
        # the ProjectManager boundary will persist it when the ledger itself
        # is available.
        pass

def fail(code, message):
    print(json.dumps({'status': code, 'error': message})); raise SystemExit(2)

def request(url, token, method='GET', payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = Request(url, data=data, method=method, headers={'Accept':'application/json','X-Rundeck-Auth-Token':token, **({'Content-Type':'application/json'} if data else {})})
    with urlopen(req, timeout=int(os.environ.get('RUNDECK_TIMEOUT_SECONDS','20'))) as response:
        return json.load(response)

def output_summary(payload):
    lines=[]
    for entry in payload.get('entries',[])[:20]:
        text=str(entry.get('log','')).strip()
        text=re.sub(r'(?i)(token|password|secret|api[_-]?key)\s*[:=]\s*\S+',r'\1=[REDACTED]',text)
        if text: lines.append(text[:300])
    return lines


def ansible_result(lines):
    """Extract optional Ansible recap counters without trusting model text."""
    changed = failed = None
    for line in lines:
        match = re.search(r"(?i)\bchanged\s*[=:]\s*(\d+)\b", line)
        if match:
            changed = int(match.group(1))
        match = re.search(r"(?i)\bfailed\s*[=:]\s*(\d+)\b", line)
        if match:
            failed = int(match.group(1))
    if changed is None and failed is None:
        return None
    result = "FAILED" if (failed or 0) > 0 else ("NO_CHANGE" if (changed or 0) == 0 else "CHANGED")
    return {"result": result, "changed": changed or 0, "failed": failed or 0}

def retryable_status(status):
    """Rundeck returns lowercase status values; tolerate API presentation changes."""
    return str(status).upper() in ('RUNNING','WAITING')

def wait_for_terminal(base, token, execution_id):
    """Poll a submitted Rundeck execution until it reaches a terminal state."""
    budget = max(0, int(os.environ.get('RUNDECK_POLL_MAX_SECONDS', '60')))
    interval = max(1, int(os.environ.get('RUNDECK_POLL_INTERVAL_SECONDS', '2')))
    deadline = time.monotonic() + budget
    detail = request(f'{base}/api/45/execution/{execution_id}', token)
    while retryable_status(detail.get('status', 'UNKNOWN')) and time.monotonic() < deadline:
        time.sleep(min(interval, max(0, deadline - time.monotonic())))
        detail = request(f'{base}/api/45/execution/{execution_id}', token)
    return detail

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--task-id', required=True); parser.add_argument('--idempotency-key', required=True)
    parser.add_argument('--job', required=True); parser.add_argument('--target', required=True)
    args=parser.parse_args()
    load_rundeck_environment()
    registry = job_registry(ROOT)
    if os.environ.get('AUTOOPS_AUTHENTICATED_ROLE') != 'runbook-operator':
        fail('PERMISSION_DENIED','Only the authenticated runbook-operator role may execute a runbook.')
    base=os.environ.get('RUNDECK_BASE_URL','').rstrip('/'); token=os.environ.get('RUNDECK_API_TOKEN','')
    if not base.startswith(('http://','https://')) or not token: fail('INPUT_ERROR','Set RUNDECK_BASE_URL and RUNDECK_API_TOKEN.')
    jobs=json.loads(registry.read_text()).get('jobs',[]); job=next((item for item in jobs if item.get('name')==args.job),None)
    if not job: fail('JOB_NOT_ALLOWED','The requested job is not published in the allowlist.')
    pattern=job.get('options',{}).get('target')
    if not pattern or not re.fullmatch(pattern,args.target): fail('INPUT_ERROR','Target does not match the published job schema.')
    parameter_summary=hashlib.sha256(json.dumps({'job':args.job,'target':args.target},sort_keys=True,separators=(',',':')).encode()).hexdigest()
    DB.parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(DB); conn.execute('CREATE TABLE IF NOT EXISTS executions (key TEXT PRIMARY KEY, task_id TEXT, job TEXT, target TEXT, execution_id TEXT, status TEXT, created_at INTEGER, parameter_summary TEXT)')
    columns={item[1] for item in conn.execute('PRAGMA table_info(executions)')}
    if 'parameter_summary' not in columns:
        conn.execute('ALTER TABLE executions ADD COLUMN parameter_summary TEXT')
        conn.commit()
    row=conn.execute('SELECT job,target,parameter_summary,execution_id,status FROM executions WHERE key=?',(args.idempotency_key,)).fetchone()
    if row and (row[0] != args.job or row[1] != args.target or (row[2] is not None and row[2] != parameter_summary)):
        conn.close()
        print(json.dumps({'task_id':args.task_id,'status':'IDEMPOTENCY_CONFLICT','error_code':'IDEMPOTENCY_CONFLICT','retryable':False})); return 2
    if row and not row[3]:
        conn.execute('UPDATE executions SET status=? WHERE key=?', ('RESULT_UNKNOWN', args.idempotency_key)); conn.commit()
        mark_reconciling(args.task_id, args.job, args.target, args.idempotency_key)
        conn.close()
        print(json.dumps({'task_id':args.task_id,'status':'UNKNOWN','error_code':'RESULT_UNKNOWN',
                          'retry_class':'external_unknown','retryable':False})); return
    try:
        execution_id = None
        reconciliation = bool(row)
        if row:
            execution_id=row[3]
        else:
            conn.execute('INSERT INTO executions (key,task_id,job,target,execution_id,status,created_at,parameter_summary) VALUES (?,?,?,?,?,?,?,?)',(args.idempotency_key,args.task_id,args.job,args.target,None,'INTENT_RECORDED',int(time.time()),parameter_summary)); conn.commit()
            started=request(f'{base}/api/45/job/{job["id"]}/run',token,'POST',{'options':{'target':args.target}})
            execution_id=str(started['id']); conn.execute('UPDATE executions SET execution_id=?,status=? WHERE key=?',(execution_id,'RUNNING',args.idempotency_key)); conn.commit()
        detail=wait_for_terminal(base, token, execution_id)
        status=detail.get('status','UNKNOWN'); conn.execute('UPDATE executions SET status=? WHERE key=?',(status,args.idempotency_key)); conn.commit()
        if str(status).upper() == 'UNKNOWN':
            conn.execute('UPDATE executions SET status=? WHERE key=?', ('RESULT_UNKNOWN', args.idempotency_key)); conn.commit()
            mark_reconciling(args.task_id, args.job, args.target, args.idempotency_key, execution_id,
                             'Rundeck returned an unknown execution status')
            print(json.dumps({'task_id':args.task_id,'status':'UNKNOWN','error_code':'RESULT_UNKNOWN',
                              'retry_class':'external_unknown','external_execution_id':execution_id,
                              'retryable':False})); return 1
        output=request(f'{base}/api/45/execution/{execution_id}/output',token)
        summary = output_summary(output)
        payload = {'task_id':args.task_id,'status':status,'external_execution_id':execution_id,
                   'output_summary':summary,'observed_at':int(time.time()),
                   'retryable':retryable_status(status), 'reconciliation': reconciliation}
        recap = ansible_result(summary)
        if recap is not None:
            payload['ansible_recap'] = recap
        print(json.dumps(payload))
    except (HTTPError,URLError,TimeoutError,KeyError) as error:
        conn.execute('UPDATE executions SET status=? WHERE key=?', ('RESULT_UNKNOWN', args.idempotency_key)); conn.commit()
        mark_reconciling(args.task_id, args.job, args.target, args.idempotency_key, execution_id, error)
        print(json.dumps({'task_id':args.task_id,'status':'UNKNOWN','error_code':'RESULT_UNKNOWN',
                          'retry_class':'external_unknown','retryable':False,'error':str(error)})); raise SystemExit(1)
    finally: conn.close()
if __name__=='__main__': raise SystemExit(main())
