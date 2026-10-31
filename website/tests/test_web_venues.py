"""Series filtering happens before pagination and never modifies stored metadata."""
import hashlib
import json
from contextlib import closing
import pytest
pytest.importorskip('argon2', reason='Install the web extra to run browser-interface tests')
from starlette.testclient import TestClient
from cirdc.config import Config
from cirdc.web.app import create_app
from cirdc.web.index import initialize, put_rows, search, save_meta
from cirdc.web.settings import connect
from cirdc.web.venues import attach_series, parse_venue_any
from test_web import signin


@pytest.fixture
def publications(tmp_path, monkeypatch):
    monkeypatch.setenv('CIRDC_WEB_STATE', str(tmp_path / 'web'))
    values = [('101','4',1966,'Journals'),('102','81',1999,'Journals'),
              ('103','8919',2025,'Journals'),('104','600',2020,'Conferences'),
              ('105','601',2026,'Conferences'),('106','43',2025,'Journals')]
    rows = [{'number':n,'data':json.dumps({'articleTitle':'RF study '+n,'publicationNumber':v,
             'publicationYear':str(y),'articleContentType':k,'authors':[{'id':'11','preferredName':'Alex Kim'}]}),
             'abstract_state':'pending','keywords_state':'pending','updated_at':'2026-10-28 10:00:00'}
            for n,v,y,k in values]
    with closing(connect('search.sqlite')) as db:
        initialize(db);put_rows(db,rows)
        db.executemany('INSERT INTO venue_members VALUES(?,?,?)',
                       [('Journals',v,v) for _,v,_,k in values if k=='Journals']+
                       [('Conferences','1000708','600'),('Conferences','1000708','601')])
        save_meta(db,phase='ready',authors_phase='ready',checked_at='2099-01-01T00:00:00+00:00')
        db.commit()
    return tmp_path,rows


def numbers(params):
    return {p['number'] for p in search(params)['items']}


def test_multi_publication_union_includes_editions_and_historical_journal_ids(publications):
    assert numbers({'venue_any':'4,1000708'})=={'101','104','105'}
    assert numbers({'venue_any':'81,8919'})=={'102','103'}
    assert numbers({'venue_any':'43'})=={'106'}
    assert not numbers({'venue_any':'999'})


def test_multi_publication_filter_combines_with_fulltext_author_and_existing_facets(publications):
    assert numbers({'venue_any':'4,1000708','q':'RF','field':'title','kind':'Conferences','year_from':'2025'})=={'105'}
    assert numbers({'venue_any':'4,1000708','venue':'1000708'})=={'104','105'}
    assert numbers({'venue_any':'4,1000708','q':'11','field':'authors'})=={'101','104','105'}
    assert numbers({'venue_any':'4','venue':'1000708'})==set()


def test_multi_publication_pagination_has_no_missing_or_duplicate_records(publications):
    params={'venue_any':'4,1000708','limit':'2','sort':'year'}
    first=search(params);second=search({**params,'cursor':first['next_cursor']})
    assert [p['number'] for p in first['items']+second['items']]==['105','104','101']
    with pytest.raises(ValueError):
        search({**params,'venue_any':'81','cursor':first['next_cursor']})


@pytest.mark.parametrize('value',['4,,5','4;DROP TABLE docs','-1',','.join(str(i) for i in range(33)),'1'*65])
def test_multi_publication_input_is_bounded_and_parameterized(value):
    with pytest.raises(ValueError):parse_venue_any(value)


def test_series_attachment_uses_read_only_connection_and_preserves_database(publications):
    root,_=publications
    path=root/'web/search.sqlite';before=hashlib.sha256(path.read_bytes()).hexdigest()
    items=[{'kind':'Conferences','venue':'601'},
           {'record':{'articleContentType':'Early Access Articles','publicationNumber':'4'}}]
    attach_series(items)
    assert items[0]['venue_series']==['1000708']
    assert items[1]['venue_series']==['4']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==before
    assert parse_venue_any('4, 4,1000708')==['4','1000708']


def test_all_paper_endpoints_return_series_and_exact_lookup_respects_scope(publications,monkeypatch):
    import cirdc.web.app as module
    root,rows=publications
    class Canonical:
        def __init__(self,config):pass
        def execute(self,sql,args=()):return [dict(r) for r in rows if r['number']==args[0]]
        def close(self):pass
    monkeypatch.setattr(module,'Store',Canonical)
    app=create_app(Config(root,root/'runtime',{}))
    app.state.accounts.create('reader','fixture-venue-password')
    app.state.accounts.reset('reader','fixture-venue-password',False)
    with TestClient(app) as client:
        assert client.get('/api/papers?venue_any=4').status_code==401
        signin(client,'reader','fixture-venue-password')
        result=client.get('/api/papers?venue_any=4,1000708').json()
        assert {p['number'] for p in result['items']}=={'101','104','105'}
        assert next(p for p in result['items'] if p['number']=='105')['venue_series']==['1000708']
        assert client.get('/api/papers/105').json()['paper']['venue_series']==['1000708']
        assert client.get('/api/papers?q=105&venue_any=1000708').json()['items'][0]['venue_series']==['1000708']
        assert client.get('/api/papers?q=105&venue_any=4').json()['items']==[]
        assert client.get('/api/papers?q=105&venue=1000708&venue_any=4,1000708').json()['items']
        assert client.get('/api/papers?q=105&venue_any=4,,5').status_code==422


def test_new_conference_edition_is_resolved_without_a_frontend_mapping_change(publications):
    assert numbers({'venue_any':'1000708'})=={'104','105'}
    with closing(connect('search.sqlite')) as db:
        put_rows(db,[{'number':'107','data':{'articleTitle':'New edition','publicationNumber':'602',
            'publicationYear':'2027','articleContentType':'Conferences'},
            'abstract_state':'pending','keywords_state':'pending'}])
        db.execute('INSERT INTO venue_members VALUES(?,?,?)',('Conferences','1000708','602'))
        db.commit()
    assert numbers({'venue_any':'1000708'})=={'104','105','107'}
    item={'kind':'Conferences','venue':'602'};attach_series([item])
    assert item['venue_series']==['1000708']
