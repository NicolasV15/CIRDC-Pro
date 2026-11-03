import pytest
from starlette.testclient import TestClient
from cirdc.web import maintenance
from cirdc.web.app import create_app
from test_web import website

def test_single_paper_get_is_read_only_and_post_requires_same_origin(website,monkeypatch):
    website.web["maintenance"]={"enabled":True}
    calls=[]
    def call(config,operation,number=None):
        calls.append(operation)
        return {"number":number,"abstract_state":"pending","keywords_state":"complete","job":{"status":"pending"}}
    monkeypatch.setattr(maintenance,"call",call)
    with TestClient(create_app(website,reader_auth="public")) as client:
        assert client.get("/api/papers/100/metadata/status").status_code==200
        assert calls==["metadata_read"]
        assert client.post("/api/papers/100/metadata/ensure",json={}).status_code==403
        assert client.post("/api/papers/100/metadata/ensure",json={},headers={"Origin":"http://testserver"}).status_code==200
        assert calls==["metadata_read","metadata_ensure"]
        assert client.get("/api/admin/maintenance").status_code==404
    website.web["maintenance"]["enabled"]=False
    with TestClient(create_app(website,reader_auth="public")) as client:
        assert client.get("/api/papers/100/metadata/status").json()["state"]=="disabled"
        assert client.post("/api/papers/100/metadata/ensure",json={},headers={"Origin":"http://testserver"}).status_code==405

def test_failed_coordinator_does_not_expose_private_diagnostics(website,monkeypatch):
    website.web["maintenance"]={"enabled":True}
    def call(*args,**kwargs):raise RuntimeError("private-secret")
    monkeypatch.setattr(maintenance,"call",call)
    with TestClient(create_app(website,reader_auth="public")) as client:
        response=client.get("/api/papers/100/metadata/status")
        assert response.status_code==503
        assert "private-secret" not in response.text

@pytest.mark.parametrize("stage",["references","citations","unknown"])
def test_compatibility_engine_never_locks_spawns_or_mutates_relation_runs(stage):
    from types import SimpleNamespace
    from cirdc.engine import Service
    class NeverWrite:
        def run(self,number):return {"params":{"stage":stage}}
        def __getattr__(self,name):raise AssertionError("Unexpected write/lock: "+name)
    service=Service.__new__(Service);service.store=NeverWrite();service.config=SimpleNamespace(web={})
    for operation in (lambda:service.start({"stage":stage}),
                      lambda:service.resume("id"),lambda:service.resume("id",retry=True),lambda:service.work("id")):
        with pytest.raises(ValueError,match="coordinator"):operation()

def test_managed_compatibility_api_rejects_bulk_before_opening_database(website,monkeypatch):
    from cirdc import api
    website.web["maintenance"]={"enabled":True}
    def forbidden(*a,**k):raise AssertionError("Database should not be opened")
    monkeypatch.setattr(api,"Store",forbidden)
    for action in ("update","resume","retry"):
        value=api.invoke(action,website,run_id="existing")
        assert value["status"]=="error" and "coordinator" in value["message"]
