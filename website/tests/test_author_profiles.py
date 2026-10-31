"""Offline format/HTTP tests and connection-local MySQL fault recovery tests."""
import os
from datetime import datetime, timedelta, timezone

import pytest
import requests

from cirdc.author_profiles import (
    AuthorClient,
    AuthorError,
    AuthorRepository,
    atomic_write,
    author_lock,
    encoded,
    envelope,
    identity,
    read_snapshot,
    validate,
)
from cirdc.config import Config

AID = '37086128853'


def raw(aid=AID):
    return [{'idStr': aid, 'preferredName': 'Example Researcher', 'firstName': 'Example',
             'lastName': 'Researcher', 'currentAffiliations': [], 'bioParagraphs': [
                 'Analog &amp; RF<br>Research.<img src="https://example.invalid/photo.jpg">'
                 '<script>bad()</script> https://example.invalid/avatar/1'],
             'photoUrl': 'https://example.invalid/photo.jpg', 'articleCount': 19, 'citations': '276',
             'isHideProfile': False, 'coAuthors': [{'idStr': '9007199254740993',
                 'preferredName': 'Same Name', 'photoUrl': 'https://example.invalid/photo.jpg'}],
             'topics': [{'name': 'RF', 'numRecords': 2}], 'publicationYears': [
                 {'id': 'PublicationYear:2026', 'name': '2026', 'numRecords': 2}]}]


def snapshot():
    return envelope(raw(), AID)


def test_portable_profile_excludes_images_and_preserves_missing_vs_empty(tmp_path):
    value = snapshot()
    assert value['profile']['bio_paragraphs'] == ['Analog & RF\nResearch.']
    assert value['profile']['coauthors'][0]['author_id'] == '9007199254740993'
    assert value['field_states']['orcid'] == 'not_returned'
    assert value['field_states']['current_affiliations'] == 'no_data'
    assert not any(word in encoded(value).decode().lower() for word in ('photourl', 'avatar', '<img', 'bad()'))
    path = tmp_path / 'profile.json'
    atomic_write(path, value)
    assert path.stat().st_mode & 0o777 == 0o600
    assert read_snapshot(path) == value


@pytest.mark.parametrize('value', [None, {}, [], [{'idStr': AID}], raw('123'), raw()+raw()])
def test_unexpected_payload_is_never_successful_empty(value):
    with pytest.raises(AuthorError):
        envelope(value, AID)


@pytest.mark.parametrize('aid', [True, 123, None, '../1', '', '1 OR 1=1', 'a', '1'*65])
def test_identity_is_string_only_and_not_a_query(aid):
    with pytest.raises(AuthorError):
        identity(aid)


def test_hidden_profile_is_a_valid_source_observation():
    value = envelope([{'idStr': AID, 'isHideProfile': True}], AID)
    assert validate(value)['profile']['is_hidden'] is True


def test_snapshot_tampering_and_time_validation(tmp_path):
    value = snapshot()
    value['profile']['preferred_name'] = 'tampered'
    with pytest.raises(AuthorError, match='snapshot_digest_mismatch'):
        validate(value)
    for stamp in (None, 'yesterday', '2026-01-01', (datetime.now(timezone.utc)+timedelta(days=1)).isoformat()):
        value = snapshot(); value['fetched_at'] = stamp
        with pytest.raises(AuthorError):
            validate(value)
    path = tmp_path / 'large.json';path.write_bytes(b'x'*(4*1024*1024+1))
    with pytest.raises(AuthorError, match='snapshot_too_large'):
        read_snapshot(path)


def test_atomic_export_keeps_old_file_on_interruption(tmp_path, monkeypatch):
    path = tmp_path / 'author.json';atomic_write(path, snapshot());before = path.read_bytes()
    def interrupted(*args):
        raise OSError('disk full')
    monkeypatch.setattr(os, 'replace', interrupted)
    with pytest.raises(OSError):
        atomic_write(path, {'new': 'value'})
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]


class Reply:
    def __init__(self, status=200, data=None, html=False):
        self.status_code=status
        self.headers={'Content-Type': 'text/html' if html else 'application/json'}
        self.body=b'<html>entry</html>' if html else encoded(raw() if data is None else data)
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def iter_content(self, size):
        yield self.body


class Session:
    def __init__(self, replies):
        self.headers={'Content-Type': 'application/json'}
        self.replies=iter(replies);self.calls=[];self.closed=False
    def get(self, url, **kwargs):
        self.calls.append((url,kwargs));reply=next(self.replies)
        if isinstance(reply, Exception):
            raise reply
        return reply
    def close(self):
        self.closed=True


def test_normal_session_entry_then_bounded_json_retry(tmp_path, monkeypatch):
    monkeypatch.setattr('cirdc.author_profiles.time.sleep', lambda x: None)
    session=Session([Reply(html=True), Reply(502), Reply()])
    value=AuthorClient(Config(tmp_path,tmp_path,{}),session).fetch(AID)
    assert value['author_id']==AID and session.closed
    assert session.calls[0][0].endswith('/search/searchresult.jsp')
    assert len(session.calls)==3 and 'Content-Type' not in session.headers
    assert all(k['timeout']==(5,30) and not k['allow_redirects'] for _,k in session.calls)


@pytest.mark.parametrize('status', [202,401,403,418,429])
def test_access_challenge_is_not_empty_and_not_retried(tmp_path, monkeypatch, status):
    monkeypatch.setattr('cirdc.author_profiles.time.sleep', lambda x: None)
    session=Session([Reply(html=True),Reply(status)])
    with pytest.raises(AuthorError, match='access_restricted') as error:
        AuthorClient(Config(tmp_path,tmp_path,{}),session).fetch(AID)
    assert error.value.http_status==status and len(session.calls)==2


def test_network_retries_are_finite_and_html_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr('cirdc.author_profiles.time.sleep', lambda x: None)
    session=Session([requests.Timeout() for _ in range(3)])
    with pytest.raises(AuthorError, match='network_error'):
        AuthorClient(Config(tmp_path,tmp_path,{}),session).fetch(AID)
    assert len(session.calls)==3 and session.closed
    session=Session([Reply(html=True),Reply(html=True)])
    with pytest.raises(AuthorError, match='unexpected_content_type'):
        AuthorClient(Config(tmp_path,tmp_path,{}),session).fetch(AID)


def test_fetch_dispatch_does_not_open_mysql(tmp_path, monkeypatch):
    from cirdc.author_cli import invoke_author
    monkeypatch.setattr(AuthorClient,'fetch',lambda self, aid:snapshot())
    def forbidden(*args):
        raise AssertionError('fetch opened MySQL')
    monkeypatch.setattr('cirdc.store.Store',forbidden)
    path=tmp_path/'one.json'
    result=invoke_author('fetch',Config(tmp_path,tmp_path,{}),author_id=AID,output=str(path))
    assert result['status']=='fetched' and read_snapshot(path)['author_id']==AID


@pytest.fixture
def repository(tmp_path, monkeypatch):
    if os.environ.get('CIRDC_INTEGRATION')!='1':
        pytest.skip('Enable configured MySQL integration for connection-local author tables')
    from cirdc.author_schema import ddl
    from cirdc.store import Store
    store=Store(Config.load())
    store.execute(ddl().replace('CREATE TABLE authors', 'CREATE TEMPORARY TABLE authors'))
    monkeypatch.setattr('cirdc.author_schema.check',lambda s:True)
    repo=AuthorRepository(store,tmp_path)
    yield repo
    store.db.rollback();store.close()


def test_import_is_idempotent_and_stale_cannot_replace_new(repository):
    value=snapshot();repository.save(value);repository.save(value)
    assert repository.store.execute('SELECT COUNT(*) AS n FROM authors')[0]['n']==1
    value['fetched_at']=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()
    assert repository.save(value)['status']=='stale'
    assert len(list(repository.state_dir.rglob('*.json')))==1


def test_failed_refresh_preserves_success_and_hidden_suppresses_details(repository):
    repository.save(snapshot())
    repository.failed(AID,AuthorError('access_restricted',418),datetime.now(timezone.utc).isoformat())
    saved=repository.show(AID,public=True)
    assert saved['fetch_state']=='blocked' and saved['profile']['preferred_name']=='Example Researcher'
    assert saved['last_http_status']==418 and saved['fetched_at']
    value=envelope([{'idStr':AID,'isHideProfile':True}],AID)
    repository.save(value)
    assert repository.show(AID,public=True)['profile']=={'is_hidden':True}


def test_database_commit_failure_leaves_recoverable_snapshot(repository,monkeypatch):
    original=repository.store.db.commit
    def fail():
        raise OSError('simulated commit failure')
    monkeypatch.setattr(repository.store.db,'commit',fail)
    with pytest.raises(OSError):
        repository.save(snapshot())
    assert repository.row(AID) is None
    files=list(repository.state_dir.rglob('*.json'));assert len(files)==1
    monkeypatch.setattr(repository.store.db,'commit',original)
    assert repository.save(read_snapshot(files[0]))['status']=='saved'


def test_disk_failure_leaves_database_untouched(repository,monkeypatch):
    def fail(*args):
        raise OSError('disk full')
    monkeypatch.setattr('cirdc.author_profiles.atomic_write',fail)
    with pytest.raises(OSError):
        repository.save(snapshot())
    assert repository.row(AID) is None


def test_two_database_connections_cannot_write_same_author(repository):
    from cirdc.store import Store
    other=Store(Config.load())
    try:
        with author_lock(repository.store,AID), pytest.raises(AuthorError,match='author_write_busy'):
            with author_lock(other,AID):
                pytest.fail('competing writer acquired author lock')
        with author_lock(other,AID):
            pass
    finally:
        other.close()


def test_profile_api_requires_login_and_never_fetches(tmp_path,monkeypatch):
    pytest.importorskip('argon2', reason='Install the web extra for browser tests')
    from starlette.testclient import TestClient
    from test_web import signin

    from cirdc.web.app import create_app
    monkeypatch.setenv('CIRDC_WEB_STATE',str(tmp_path/'web'))
    config=Config(tmp_path,tmp_path,{})
    class DummyStore:
        def __init__(self,*args):
            pass
        def close(self):
            pass
        def execute(self, *args):
            return []
    monkeypatch.setattr('cirdc.web.app.Store',DummyStore)
    monkeypatch.setattr(AuthorRepository,'show',lambda self,aid,public:None)
    def no_fetch(*args):
        pytest.fail('page triggered source retrieval')
    monkeypatch.setattr(AuthorClient,'fetch',no_fetch)
    app=create_app(config)
    app.state.accounts.create('alice','fixture-password')
    app.state.accounts.reset('alice','fixture-password',must_change=False)
    with TestClient(app) as client:
        path='/api/author-profiles/ieee/'+AID
        assert client.get(path).status_code==401
        signin(client,'alice','fixture-password')
        assert client.get(path).json()['status']=='not_fetched'
        assert client.post(path,headers={'Origin':'http://testserver'}).status_code in (403,405)
        assert client.get('/api/author-profiles/other/'+AID).status_code==422


def test_record_creation_time_uses_utc_even_if_server_defaults_to_local(repository):
    repository.save(snapshot())
    row=repository.row(AID)
    now=datetime.now(timezone.utc).replace(tzinfo=None)
    assert abs((row['created_at']-now).total_seconds())<5
    assert abs((row['updated_at']-now).total_seconds())<5
    assert repository.store.execute('SELECT @@SESSION.time_zone AS zone')[0]['zone']=='+00:00'
