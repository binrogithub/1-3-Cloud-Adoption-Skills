#!/usr/bin/env python3
import argparse, datetime as dt, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(); p.add_argument('--host',required=True); p.add_argument('--service',required=True); p.add_argument('--action',required=True); p.add_argument('--policy',default=ROOT/'config/authorization/service-policy.json'); a=p.parse_args()
policy=json.loads(Path(a.policy).read_text())
expiry=policy.get('expires_at','')
if expiry.startswith('replace-') or dt.datetime.fromisoformat(expiry.replace('Z','+00:00')) <= dt.datetime.now(dt.timezone.utc): raise SystemExit('authorization is absent or expired')
if a.host not in policy['allowed_hosts'] or a.service not in policy['allowed_services'] or a.action not in policy['actions']: raise SystemExit('authorization scope denied')
print(json.dumps({'authorized':True,'host':a.host,'service':a.service,'action':a.action}))
