"""Bounded operator qualification; no automatic retries of failed identities."""
import argparse
import json
import subprocess
import time
from pathlib import Path
from cirdc.author_jobs import Bridge
from cirdc.author_profiles import atomic_write


def counts(rows):
    return {state:sum(row.get('state')==state for row in rows) for state in
            ('missing','queued','fetching','complete','hidden','blocked','failed')}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',required=True)
    parser.add_argument('--manifest',required=True)
    parser.add_argument('--evidence',required=True)
    parser.add_argument('--enable-background',action='store_true')
    parser.add_argument('--service',default='cirdc-multinode.service')
    args=parser.parse_args()
    cfg=json.loads(Path(args.config).read_text())
    identities=json.loads(Path(args.manifest).read_text())
    if len(identities)!=1000 or len(set(identities))!=1000:raise ValueError('Expected 1000 unique frozen identities')
    bridge=Bridge({**cfg['jobs']['authors'],'coordinator_state':cfg['state_dir']})
    evidence=Path(args.evidence);evidence.mkdir(parents=True,exist_ok=True)
    try:
        for size in (100,1000):
            selected=identities[:size]
            for aid in selected:
                if bridge.queue.read(aid)['state']=='missing':bridge.enqueue(aid,trigger='manual')
            atomic_write(Path(cfg['state_dir'])/'wake.json',{'at':time.time()})
            while True:
                rows=[]
                for aid in selected:
                    row=bridge.queue.read(aid)
                    if row['state']=='missing':
                        old=bridge.profile(aid)
                        if old and old.get('fetched_at'):row={**row,'state':'hidden' if old['profile'].get('is_hidden') else 'complete'}
                    rows.append(row)
                summary=counts(rows)
                terminal=sum(summary[k] for k in ('complete','hidden','blocked','failed'))
                completed=sorted((r for r in rows if r['state'] in ('complete','hidden','blocked','failed')),key=lambda r:r.get('updated',0))
                restricted=len(completed)>=3 and all(r['state']=='blocked' for r in completed[-3:])
                report={'stage':size,'finished':terminal,'counts':summary,'updated':time.time(),
                        'status':'source_restricted' if restricted else 'observing','results':rows}
                atomic_write(evidence/'qualification.json',report)
                if restricted:
                    bridge.queue.control('pause');return
                if terminal==size:break
                time.sleep(10)
            invalid=any(r.get('error') in ('author_identity_mismatch','invalid_author_response','parse_failed','invalid_fetch_time','stale_author_observation') for r in rows)
            failures=summary['blocked']+summary['failed']
            if invalid or failures/size>.05:
                atomic_write(evidence/'qualification.json',{**report,'status':'quality_gate_failed'});return
            coverage={}
            for aid in selected:
                profile=bridge.profile(aid)
                if profile:
                    for field,state in profile['field_states'].items():
                        coverage.setdefault(field,{});coverage[field][state]=coverage[field].get(state,0)+1
            atomic_write(evidence/f'qualification-{size}.json',{**report,'status':'passed','field_coverage':coverage})
        if args.enable_background:
            if not (evidence/'website-deployed.json').exists():
                atomic_write(evidence/'qualification.json',{**report,'status':'passed_awaiting_website_deployment'})
                return
            current=json.loads(Path(args.config).read_text())
            if current['jobs']['authors']['queue']!=cfg['jobs']['authors']['queue']:raise RuntimeError('Author target changed during qualification')
            current['jobs']['authors']['background_enabled']=True
            atomic_write(args.config,current)
            subprocess.run(['systemctl','--user','restart',args.service],check=True)
        atomic_write(evidence/'qualification.json',{**report,'status':'passed','background_enabled':args.enable_background})
    finally:bridge.close()

if __name__=='__main__':main()
