from contextlib import closing
import pytest
from cirdc.web.settings import connect
from cirdc.web.index import initialize, put_rows, search, save_meta
from cirdc.web.authors import find_authors, author_references, get_author


@pytest.fixture
def people(tmp_path, monkeypatch):
    monkeypatch.setenv('CIRDC_WEB_STATE', str(tmp_path))
    rows = [
        ('1', [{'id': 11, 'preferredName': 'Alex Kim'}]),
        ('2', [{'id': 22, 'preferredName': 'Alex Kim'}]),
        ('3', [{'id': '11', 'preferredName': 'Alexander Kim'}]),
        ('4', [{'preferredName': 'Alex Kim'}]),
        ('5', [{'id': 33, 'preferredName': 'Alex Lee'}, {'id': 44, 'preferredName': 'Jamie Kim'}]),
    ]
    with closing(connect('search.sqlite')) as db:
        initialize(db)
        put_rows(db, [{'number': n, 'data': {'articleTitle': 'Study '+n,'publicationYear': '2025', 'authors': a},
                       'abstract_state': 'pending', 'keywords_state': 'pending'} for n,a in rows])
        save_meta(db, phase='ready', authors_phase='ready', checked_at='2099-01-01T00:00:00+00:00')
        db.commit()


def test_homonyms_remain_separate_and_aliases_share_only_the_source_id(people):
    result = find_authors({'q': 'Alex Kim'})
    assert {p['author_id'] for p in result['items']} == {'11', '22'}
    assert result['unidentified_papers'] == 1
    first = get_author('ieee', '11')
    assert first['papers'] == 2
    assert set(first['name_variants']) == {'Alex Kim','Alexander Kim'}
    assert first['profile_ref'] == {'source':'ieee','author_id':'11'}


def test_selected_identity_includes_name_variants_and_excludes_homonyms(people):
    result = search({'q':'Alex Kim','field':'authors','author_source':'ieee','author_id':'11'})
    assert {p['number'] for p in result['items']} == {'1','3'}
    assert {p['number'] for p in search({'q':'22','field':'authors'})['items']} == {'2'}
    assert search({'q':'Study','field':'title'})['partial'] is False
    assert search({'q':'Study','field':'title'})['partial'] is False


def test_name_words_must_belong_to_one_signature_and_missing_ids_are_not_people(people):
    numbers = {p['number'] for p in search({'q':'Alex Kim','field':'authors'})['items']}
    assert numbers == {'1','2','3','4'}
    unknown = search({'q':'Alex Kim','field':'authors','author_unidentified':'1'})
    assert [p['number'] for p in unknown['items']] == ['4']


def test_author_ids_are_lossless_strings_and_original_order_is_preserved():
    refs = author_references({'authors':[{'id':9007199254740995,'preferredName':'First'},
                                       {'id':'22','preferredName':'Second'},{'preferredName':'Third'}]})
    assert refs[0]['author_id'] == '9007199254740995'
    assert [r['ordinal'] for r in refs] == [0,1,2]
    assert refs[-1]['author_id'] is None


def test_identity_changes_and_deleted_papers_remove_old_relationships(people):
    with closing(connect('search.sqlite')) as db:
        put_rows(db,[{'number':'1','data':{'authors':[{'id':'22','preferredName':'Alex Kim'}]},
                      'abstract_state':'pending','keywords_state':'pending'}])
        db.commit()
        assert get_author('ieee','11')['papers'] == 1
        db.execute('DELETE FROM docs WHERE number=?',('3',));db.commit()
        assert get_author('ieee','11')['papers'] == 0
    assert {p['author_id'] for p in find_authors({'q':'Alex Kim'})['items']} == {'22'}


def test_author_endpoints_are_authenticated_and_id_search_is_not_a_paper_lookup(people,tmp_path):
    from starlette.testclient import TestClient
    from cirdc.config import Config
    from cirdc.web.app import create_app
    app=create_app(Config(tmp_path,tmp_path/'runtime',{}))
    app.state.accounts.create('reader','fixture-personal-password')
    app.state.accounts.reset('reader','fixture-personal-password',False)
    with TestClient(app) as client:
        assert client.get('/api/authors?q=Alex').status_code==401
        token=client.get('/api/auth/session').json()['csrf']
        r=client.post('/api/auth/login',json={'username':'reader','password':'fixture-personal-password'},
                      headers={'Origin':'http://testserver','X-CSRF-Token':token})
        assert r.status_code==200
        authors=client.get('/api/authors?q=Alex+Kim').json()
        assert {a['author_id'] for a in authors['items']}=={'11','22'}
        papers=client.get('/api/papers?field=authors&q=11').json()
        assert {p['number'] for p in papers['items']}=={'1','3'}
        assert all(p['author_refs'][0]['author_id']=='11' for p in papers['items'])
        assert client.get('/api/authors/ieee/11').json()['author']['profile_ref']=={'source':'ieee','author_id':'11'}
        assert client.get('/api/authors/orcid/11').status_code==422


def test_author_backfill_resumes_and_consolidates_without_duplicate_signatures(people):
    import json
    from cirdc.web.authors import backfill_step, consolidate_step
    from cirdc.web.index import metadata
    class Transaction:
        def rollback(self): pass
        def commit(self): pass
    class Source:
        db=Transaction()
        def execute(self,sql,args):
            last,limit=args
            return [dict(number=str(i),author_data=json.dumps([{'id':'11','preferredName':'Alex Kim'}]))
                    for i in range(1,6) if str(i)>last][:limit]
    with closing(connect('search.sqlite')) as db:
        save_meta(db,authors_phase='building')
        db.commit()
        assert backfill_step(Source(),db,2)
        assert metadata(db)['authors_last_number']=='2'
    with closing(connect('search.sqlite')) as db:
        while metadata(db)['authors_phase']=='building':
            backfill_step(Source(),db,2)
        while metadata(db)['authors_phase']=='consolidating':
            consolidate_step(db,metadata(db),1)
        assert metadata(db)['authors_phase']=='name_search'
        backfill_step(Source(),db,2)
        assert metadata(db)['authors_papers_seen']==5
        assert db.execute('SELECT COUNT(*) FROM paper_authors').fetchone()[0]==5
        assert get_author('ieee','11')['papers']==5
        assert not backfill_step(Source(),db,2)
        assert find_authors({'q':'Alex Kim'})['items'][0]['papers']==5
        put_rows(db,[{'number':'5','data':{'authors':[{'id':'55','preferredName':'Post Build Name'}]},
                      'abstract_state':'pending','keywords_state':'pending'}]);db.commit()
        assert find_authors({'q':'Post Build Name'})['items'][0]['author_id']=='55'


def test_paper_results_expose_ordered_identity_links_without_loading_canonical_payloads(people):
    from cirdc.web.authors import attach_author_references
    items=[{'number':'5'},{'number':'4'},{'number':'unknown'}]
    attach_author_references(items)
    assert [a['author_id'] for a in items[0]['author_refs']]==['33','44']
    assert [a['ordinal'] for a in items[0]['author_refs']]==[0,1]
    assert items[1]['author_refs'][0]['author_id'] is None
    assert items[1]['author_refs'][0]['name']=='Alex Kim'
    assert items[2]['author_refs']==[]
    with closing(connect('search.sqlite')) as db:
        put_rows(db,[{'number':'1','data':{'authors':[{'id':9007199254740995,'preferredName':'Large ID'}]},
                      'abstract_state':'pending','keywords_state':'pending'}]);db.commit()
    page=[{'number':'1'}];attach_author_references(page)
    assert page[0]['author_refs'][0]['author_id']=='9007199254740995'
