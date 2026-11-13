from datetime import datetime,timezone
from types import SimpleNamespace
import pytest
import cirdc.author_jobs as jobs
import cirdc.author_profiles as profiles


def test_validated_job_uses_internal_write_once(tmp_path,monkeypatch):
    b=jobs.Bridge.__new__(jobs.Bridge);b.queue=jobs.Queue(tmp_path/'jobs.sqlite')
    b.queue.enqueue('123');task=b.claim()
    counts={'validate':0,'write':0}
    original=profiles.validate
    def checked(value):
        counts['validate']+=1
        return original(value)
    monkeypatch.setattr(jobs,'validate',checked)
    monkeypatch.setattr(profiles,'validate',checked)
    class Repo(profiles.AuthorRepository):
        def __init__(self):pass
        def _save_validated(self,value):
            counts['write']+=1
            assert value['author_id']=='123'
            return {'status':'saved'}
        def failed(self,*a):pytest.fail('valid result rejected')
    b.repo=Repo()
    value=profiles.envelope([{'idStr':'123','preferredName':'Test'}],'123')
    assert b.apply(task,{'records':value})['status']=='complete'
    assert counts=={'validate':1,'write':1}
    assert b.apply(task,{'records':value})['status']=='stale'
    assert counts=={'validate':1,'write':1}


def test_public_save_still_validates_and_rejects_tampering(monkeypatch):
    received=[]
    repo=profiles.AuthorRepository.__new__(profiles.AuthorRepository)
    monkeypatch.setattr(repo,'_save_validated',lambda value:received.append(value) or {'status':'saved'})
    value=profiles.envelope([{'idStr':'123','preferredName':'Test'}],'123')
    assert repo.save(value)=={'status':'saved'}
    assert len(received)==1
    value['profile']['preferred_name']='tampered'
    with pytest.raises(profiles.AuthorError,match='snapshot_digest_mismatch'):repo.save(value)
    assert len(received)==1


def test_storage_errors_still_propagate_without_marking_job_complete(tmp_path):
    b=jobs.Bridge.__new__(jobs.Bridge);b.queue=jobs.Queue(tmp_path/'jobs.sqlite');b.queue.enqueue('123');task=b.claim()
    class Repo:
        def _save_validated(self,value):raise OSError('simulated storage failure')
        def failed(self,*a):pytest.fail('storage failure reclassified as source failure')
    b.repo=Repo();value=profiles.envelope([{'idStr':'123','preferredName':'Test'}],'123')
    with pytest.raises(OSError):b.apply(task,{'records':value})
    assert b.queue.read('123')['state']=='fetching'


def test_normalized_input_keeps_original_second_validation(tmp_path,monkeypatch):
    import hashlib
    b=jobs.Bridge.__new__(jobs.Bridge);b.queue=jobs.Queue(tmp_path/'jobs.sqlite');b.queue.enqueue('123');task=b.claim()
    count=[];original=profiles.validate
    def checked(value):count.append(1);return original(value)
    monkeypatch.setattr(jobs,'validate',checked)
    class Repo:
        def _save_validated(self,value):self.saved=value;return {'status':'saved'}
        def failed(self,*a):pytest.fail('valid normalized input rejected')
    b.repo=Repo()
    value=profiles.envelope([{'idStr':'123','preferredName':'Test'}],'123')
    value['profile']['preferred_name']='<b>Test</b>'
    assert b.apply(task,{'records':value})['status']=='complete'
    assert count==[1,1] and b.repo.saved['profile']['preferred_name']=='Test'


def test_non_idempotent_normalization_keeps_original_rejection_boundary(tmp_path):
    import copy,hashlib
    b=jobs.Bridge.__new__(jobs.Bridge);b.queue=jobs.Queue(tmp_path/'jobs.sqlite');b.queue.enqueue('123');task=b.claim()
    class Repo:
        def _save_validated(self,value):pytest.fail('unstable canonical profile written')
        def failed(self,*a):pytest.fail('second validation exception was reclassified')
    b.repo=Repo()
    value=profiles.envelope([{'idStr':'123','preferredName':'Test'}],'123')
    value['profile']['preferred_name']='&lt;b&gt;Test&lt;/b&gt;'
    canonical=copy.deepcopy(value['profile']);canonical['preferred_name']='<b>Test</b>'
    value['payload_sha256']=hashlib.sha256(profiles.encoded(canonical)).hexdigest()
    with pytest.raises(profiles.AuthorError,match='snapshot_digest_mismatch'):b.apply(task,{'records':value})
    assert b.queue.read('123')['state']=='fetching'


def test_candidate_preserves_original_outcomes_for_canonical_and_transformed_inputs(tmp_path):
    import copy,hashlib,importlib.util
    from pathlib import Path
    if not __import__('os').environ.get('CIRDC_AUTHOR_BASELINE_SOURCE'):pytest.skip('Set audit baseline for original/candidate parity comparison')
    original_path=Path(__import__('os').environ['CIRDC_AUTHOR_BASELINE_SOURCE'])
    spec=importlib.util.spec_from_file_location('cirdc._original_author_jobs',original_path)
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    good=profiles.envelope([{'idStr':'123','preferredName':'Test'}],'123')
    transformed=copy.deepcopy(good);transformed['profile']['preferred_name']='<b>Test</b>'
    unstable=copy.deepcopy(good);unstable['profile']['preferred_name']='&lt;b&gt;Test&lt;/b&gt;'
    canonical=copy.deepcopy(unstable['profile']);canonical['preferred_name']='<b>Test</b>'
    unstable['payload_sha256']=hashlib.sha256(profiles.encoded(canonical)).hexdigest()
    bad=copy.deepcopy(good);bad['profile']['preferred_name']='tampered'
    wrong=profiles.envelope([{'idStr':'124','preferredName':'Other'}],'124')
    values=[{'records':x} for x in (good,transformed,unstable,bad,wrong,None,{})]+[{'error':'paused'},{'error':'access_restricted'}]
    def execute(module,value,index,label):
        b=module.Bridge.__new__(module.Bridge);b.queue=module.Queue(tmp_path/(str(index)+label+'.sqlite'));b.queue.enqueue('123');task=b.claim()
        class Repo:
            saved=None
            def save(self,data):return self._save_validated(profiles.validate(data))
            def _save_validated(self,data):self.saved=data;return {'status':'saved'}
            def failed(self,*a):pass
        b.repo=Repo()
        try:outcome=('return',b.apply(task,copy.deepcopy(value)))
        except profiles.AuthorError as e:outcome=('error',e.code)
        result=(outcome,b.queue.read('123')['state'],b.repo.saved);b.queue.db.close();return result
    for i,value in enumerate(values):assert execute(old,value,i,'old')==execute(jobs,value,i,'new')
