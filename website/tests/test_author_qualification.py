"""Exercise the staged operator gates without source HTTP or service operations."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import pytest


@pytest.mark.parametrize('invalid, deployed, expected',[(False,True,'passed'),(True,True,'quality_gate_failed'),(False,False,'passed_awaiting_website_deployment')])
def test_qualification_requires_valid_trials_and_verified_deployment(tmp_path,monkeypatch,invalid,deployed,expected):
    spec=importlib.util.spec_from_file_location('author_qualification',Path(__file__).parents[1]/'tools/qualify_authors.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    ids=[str(100000+i) for i in range(1000)]
    config=tmp_path/'config.json';config.write_text(json.dumps({'state_dir':str(tmp_path),'jobs':{'authors':{'queue':'fixture'}}}))
    manifest=tmp_path/'ids.json';manifest.write_text(json.dumps(ids))
    if deployed:(tmp_path/'website-deployed.json').write_text('{}')
    class Queue:
        def read(self,aid):return {'author_id':aid,'state':'failed' if invalid and aid==ids[0] else 'complete','error':'parse_failed' if invalid and aid==ids[0] else None}
    class Bridge:
        def __init__(self,*args):
            self.queue=Queue();self.store=SimpleNamespace(db=SimpleNamespace(rollback=lambda:None))
            self.repo=SimpleNamespace(show=lambda aid:{'field_states':{'orcid':'not_returned'}})
        def profile(self,aid):return self.repo.show(aid)
        def enqueue(self,*args,**kw):raise AssertionError('existing attempts must never be automatically retried')
        def close(self):pass
    calls=[]
    monkeypatch.setattr(module,'Bridge',Bridge)
    monkeypatch.setattr(module.subprocess,'run',lambda *args,**kw:calls.append(args))
    monkeypatch.setattr('sys.argv',['qualify','--config',str(config),'--manifest',str(manifest),'--evidence',str(tmp_path),'--enable-background'])
    module.main()
    result=json.loads((tmp_path/'qualification.json').read_text())
    assert result['status']==expected
    assert bool(calls)==(expected=='passed')
    assert json.loads(config.read_text())['jobs']['authors'].get('background_enabled',False)==(expected=='passed')
