from collections import deque
import pytest
from cirdc.citation_source import fetch_citations
from cirdc.reference_source import fetch_references
from cirdc.provider import UpstreamError


def row(n,number='456'):
    return {'order':str(n),'title':'A paper','displayText':'Author <em>A paper</em>, 2026.',
            'links':{'articleNumber':number} if number else {'doi':'10.1234/example'}}


def summary(ieee=1,other=1,lists=None,**extra):
    return {'ieeeCitationCount':str(ieee),'nonIeeeCitationCount':str(other),
            'paperCitations':lists if lists is not None else {'ieee':[row(i) for i in range(1,ieee+1)],'nonIeee':[row(i,None) for i in range(1,other+1)]},**extra}


class Source:
    def __init__(self,pages,refs=True,cites=True):
        self.pages=deque(pages);self.paths=[]
        self.metadata={'articleNumber':'123','sections':{'references':refs,'citations':cites}}
    def _document_metadata(self,n):return self.metadata
    def request(self,method,path):
        if path=='/rest/document/123':return {'articleNumber':'123'}
        self.paths.append(path);value=self.pages.popleft()
        if isinstance(value,Exception):raise value
        return value


@pytest.mark.parametrize('refs,cites',[(True,True),(True,False),(False,True),(False,False)])
def test_reference_and_citation_presence_are_independent(refs,cites):
    ref=Source([{'articleNumber':'123',**({'references':[{'order':'1','text':'Reference'}]} if refs else {})}],refs,cites)
    ref.metadata['referenceCount']=1 if refs else None
    result=fetch_references(ref,'123')
    assert result['state']==('complete' if refs else 'no_data')
    assert result['source_presence']==('present' if refs else 'absent')
    incoming=fetch_citations(Source([summary() if cites else {}],refs,cites),'123')
    assert incoming['state']==('complete' if cites else 'no_data')
    assert incoming['source_presence']==('present' if cites else 'absent')


def test_zero_is_not_missing_and_other_group_may_exist_alone():
    for ieee,other in [(0,2),(2,0),(0,0)]:
        result=fetch_citations(Source([summary(ieee,other)]),'123')
        assert len(result['items'])==ieee+other
        assert result['state']==('complete' if ieee+other else 'no_data')
        if not ieee+other:assert result['empty_reason']=='zero_count'
    result=fetch_citations(Source([{}],None,None),'123')
    assert result['state']=='unavailable' and result['source_presence']=='unknown'
    assert result['counts']=={'ieee':None,'nonIeee':None}


def test_unconfirmed_sections_never_request_full_text():
    source=Source([{}],None,None)
    original=source.request
    def request(method,path):
        assert path!='/rest/document/123', 'Relationship checks must not fetch full text'
        return original(method,path)
    source.request=request
    assert fetch_citations(source,'123')['source_presence']=='unknown'
    source=Source([{'articleNumber':'123'}],None,None)
    original=source.request
    source.request=request
    assert fetch_references(source,'123')['source_presence']=='unknown'


@pytest.mark.parametrize('refs,cites',[(True,True),(True,False),(False,True),(False,False)])
def test_publisher_string_flags_and_citedby_tab_are_independent(refs,cites):
    sections={'references':str(refs).lower(),'citedby':str(cites).lower()}
    outgoing=Source([{'articleNumber':'123',**({'references':[{'order':'1','text':'Reference'}]} if refs else {})}])
    outgoing.metadata['sections']=sections
    if refs:outgoing.metadata['referenceCount']=1
    result=fetch_references(outgoing,'123')
    assert result['source_presence']==('present' if refs else 'absent')
    incoming=Source([summary() if cites else {}])
    incoming.metadata['sections']=sections
    result=fetch_citations(incoming,'123')
    assert result['source_presence']==('present' if cites else 'absent')
    if not cites:assert result['empty_reason']=='section_absent'


@pytest.mark.parametrize('sections',[{'citedby':'false','citations':'true'},{'citedby':'unknown'},{}])
def test_ambiguous_or_invalid_section_flags_remain_unknown(sections):
    source=Source([{}]);source.metadata['sections']=sections
    assert fetch_citations(source,'123')['source_presence']=='unknown'


def test_pagination_over_300_uses_correct_case_and_distinct_group_orders():
    pages=[summary(302,2,{'ieee':[row(1)],'nonIeee':[row(1,None)]})]
    for start,end in [(2,101),(102,201),(202,301),(302,302)]:
        pages.append(summary(302,2,{'ieee':[row(i) for i in range(start,end+1)]}))
    pages.append(summary(302,2,{'nonIeee':[row(2,None)]}))
    source=Source(pages);result=fetch_citations(source,'123')
    assert result['state']=='complete' and len(result['items'])==304
    assert result['items'][0]['order']==result['items'][-2]['order']==1
    assert any('type=nonIeee' in path for path in source.paths)
    assert result['items'][0]['text']=='Author A paper, 2026.'
    assert result['items'][-1]['target_kind']=='scholar'


def test_one_group_failure_does_not_erase_other_group():
    source=Source([summary(2,1,{'ieee':[row(1)],'nonIeee':[row(1,None)]}),UpstreamError('access_restricted','limited')])
    result=fetch_citations(source,'123')
    assert result['state']=='partial' and result['group_states']['nonIeee']=='complete'
    assert len(result['items'])==2


def test_missing_parent_id_is_normal_but_wrong_explicit_identity_is_not():
    assert fetch_citations(Source([summary()]),'123')['state']=='complete'
    assert fetch_citations(Source([summary(articleNumber='999')]),'123')['state']=='failed'


def test_repeated_page_and_count_drift_are_partial_not_empty():
    for bad in [summary(2,0,{'ieee':[row(1)]}),summary(3,0,{'ieee':[row(2)]})]:
        result=fetch_citations(Source([summary(2,0,{'ieee':[row(1)]}),bad]),'123')
        assert result['state']=='partial' and result['error']=='coverage_incomplete'


def test_citations_can_be_read_even_when_document_metadata_fails():
    source=Source([summary()])
    source._document_metadata=lambda n:(_ for _ in ()).throw(UpstreamError('access_restricted','metadata blocked'))
    result=fetch_citations(source,'123')
    assert result['state']=='complete' and result['metadata_error']=='access_restricted'


def test_patent_count_is_not_in_paper_counts():
    result=fetch_citations(Source([summary(1,2,patentCitationCount=99)]),'123')
    assert sum(result['counts'].values())==3 and len(result['items'])==3


def test_explicit_empty_arrays_are_distinct_from_missing_groups():
    result=fetch_citations(Source([{'paperCitations':{'ieee':[],'nonIeee':[]}}]),'123')
    assert result['state']=='no_data' and result['empty_reason']=='zero_count'
    assert result['counts']=={'ieee':0,'nonIeee':0}
    assert result['reported_counts']=={'ieee':None,'nonIeee':None}


@pytest.mark.parametrize('bad',[False,-1,'not-a-count',1.5])
def test_malformed_counter_is_not_zero_even_with_empty_array(bad):
    result=fetch_citations(Source([summary(0,0,ieeeCitationCount=bad)]),'123')
    assert result['state']=='failed' and result['group_states']['ieee']=='failed'
    assert result['counts']['ieee'] is None and result['group_states']['nonIeee']=='no_data'
