from contextlib import closing

import pytest

from cirdc.web.index import initialize, put_rows, save_meta, search
from cirdc.web.query import article_number, normalize_doi, parse, tokens
from cirdc.web.ranking import top
from cirdc.web.settings import connect

PAPERS = [
    ('101', 'A 12-bit 1-GS/s Pipelined-SAR ADC With gm-Boosted Residue Amplifier', 'Lin Zhang; Marco Rossi', 'A pipelined SAR ADC.', '10.1109/jssc.2020.3000001'),
    ('102', 'A Successive-Approximation ADC With Redundant Capacitor DAC', 'Ana Silva', 'Low-power conversion.', ''),
    ('103', 'A 10-GS/s Time-Interleaved ADC With Background Skew Calibration', 'Keiko Tanaka', 'Timing skew.', ''),
    ('104', 'A Fourth-Order ΔΣ Modulator for Audio Codecs', 'Wei Chen', 'Noise shaping.', ''),
    ('105', 'A Sigma-Delta ADC With 120-dB Dynamic Range', 'Priya Nair', 'Audio conversion.', ''),
    ('106', 'A Bang-Bang PLL With Low Jitter', 'Hyun Park', 'Digital loop filter.', ''),
    ('107', 'A BBPD-Based Clock and Data Recovery Circuit', 'Elena Petrova', 'Wireline receiver.', ''),
    ('108', 'A 112-Gb/s Wireline Transceiver', 'Omar Haddad', 'A serializer/deserializer for data centers.', ''),
    ('109', 'A 28-GHz Voltage-Controlled Oscillator', 'Yuki Sato', 'Low phase noise.', ''),
    ('110', 'Synthetic Aperture Radar Imaging With Compressed Sensing', 'Jonas Berg', 'SAR imaging with a fast ADC front end.', ''),
    ('111', 'Design of Analog CMOS Integrated Circuits Revisited', 'Behzad Razavi', 'Analog design tutorial.', ''),
    ('112', 'Analog Design Essentials for Deep-Submicron CMOS', 'Willy Sansen', 'Op amp design.', ''),
    ('113', 'Comparing Amplifier Methods', 'Sanjay Gupta', 'We extend the Razavi method to analog design of CMOS integrated circuits.', ''),
    ('114', 'The Design of Low-Jitter Fractional-N PLLs', 'Marco Rossi', 'Fractional spurs.', ''),
    ('115', 'Low-Jitter Design of Fractional-N Frequency Synthesizers', 'Lin Zhang', 'The design of PLLs.', ''),
]


@pytest.fixture
def quality_index(tmp_path, monkeypatch):
    monkeypatch.setenv('CIRDC_WEB_STATE', str(tmp_path / 'web'))
    with closing(connect('search.sqlite')) as db:
        initialize(db)
        rows = [{'number': number, 'data': {'articleTitle': title, 'authors': [{'preferredName': name.strip()} for name in authors.split(';')],
                 'abstract': abstract, 'keywords': {}, 'publicationYear': str(2010 + i), 'publicationNumber': '4', 'doi': doi,
                 'articleContentType': 'Journals'}, 'abstract_state': 'complete', 'keywords_state': 'complete'}
                for i, (number, title, authors, abstract, doi) in enumerate(PAPERS)]
        put_rows(db, rows)
        save_meta(db, phase='ready', indexed=len(rows), checked_at='2999-01-01T00:00:00+00:00', authors_phase='ready')
        db.commit()


def numbers(result):
    return [item['number'] for item in result['items']]


def test_doi_and_article_identifiers_normalize_common_forms():
    target = '10.1109/jssc.2020.3000001'
    for value in ['10.1109/JSSC.2020.3000001', 'doi:10.1109/JSSC.2020.3000001', 'DOI: 10.1109/JSSC.2020.3000001',
                  'https://doi.org/10.1109/JSSC.2020.3000001', 'http://dx.doi.org/10.1109%2FJSSC.2020.3000001',
                  'doi.org/10.1109/JSSC.2020.3000001.', ' DOI 10.1109/jssc.2020.3000001 ']:
        assert normalize_doi(value) == target, value
    assert normalize_doi('SAR ADC') is None and normalize_doi('10.1109') is None
    assert article_number('https://ieeexplore.ieee.org/document/9000001/') == '9000001'
    assert article_number('ieeexplore.ieee.org/abstract/document/42?arnumber=42') == '42'
    assert article_number('9000001') == '9000001' and article_number('SAR 9000001') is None


def alternatives(query, terms='expand'):
    return [{' '.join(option) for option in group['alternatives']} for group in parse(query, terms)]


def test_equivalent_aliases_are_explicit_and_related_terms_are_not_matched():
    sar = alternatives('SAR ADC')[0]
    assert {'sar adc', 'successive approximation adc', 'sar adcs'} <= sar and 'pipelined adc' not in sar
    assert alternatives('SAR ADC', 'exact') == [{'sar adc'}]
    assert alternatives('SAR') == [{'sar'}]  # synthetic aperture radar shares the acronym
    for spelling in ('ΔΣ ADC', 'ΣΔ ADC', 'delta-sigma ADC', 'sigma delta ADC', 'DSM ADC'):
        group = alternatives(spelling)[0]
        assert {'δσ adc', 'σδ adc', 'delta sigma adc', 'sigma delta adc', 'dsm adc'} <= group, spelling
        assert not any('modulator' in option for option in group)
    assert 'dsm' in alternatives('DSM')[0] and 'dsm' not in alternatives('ΔΣ modulator')[0]
    bbpll = parse('BBPLL')[0]
    assert {'bang bang pll', 'bb pll', 'bbpll'} <= {' '.join(o) for o in bbpll['alternatives']}
    assert 'BBPD' in bbpll['related'] and not any('pd' == o[-1] for o in bbpll['alternatives'])
    assert 'time interleaved adc' in alternatives('TI ADC')[0] and alternatives('TI') == [{'ti'}]
    assert {'serializer deserializer', 'serdes'} <= alternatives('SerDes')[0]
    assert {'voltage controlled oscillator', 'vcos'} <= alternatives('VCO')[0]
    assert alternatives('"SAR ADC" calibration') == [{'sar adc'}, {'calibration'}]
    assert tokens('ﬁlter ΔΣ Naïve') == ['filter', 'δσ', 'naive']


def test_metadata_search_expands_equivalents_without_widening_to_related_or_separate_words(quality_index):
    assert set(numbers(search({'q': 'SAR ADC'}))) == {'101', '102'}
    assert numbers(search({'q': 'SAR ADC', 'terms': 'exact'})) == ['101']
    assert '110' not in numbers(search({'q': 'SAR ADC'}))  # SAR imaging plus an ADC is not a SAR ADC
    assert numbers(search({'q': 'ΣΔ ADC'})) == ['105'] == numbers(search({'q': 'DSM ADC'}))
    assert numbers(search({'q': 'ΔΣ modulator'})) == ['104']
    assert numbers(search({'q': 'BBPLL'})) == ['106'] and numbers(search({'q': 'BBPD'})) == ['107']
    assert numbers(search({'q': 'TI ADC'})) == ['103'] and numbers(search({'q': 'SerDes'})) == ['108']
    assert numbers(search({'q': 'VCO'})) == ['109']
    assert search({'q': 'SAR ADC'})['query']['groups'][0]['kind'] == 'concept'
    with pytest.raises(ValueError):
        search({'q': 'SAR ADC', 'terms': 'loose'})


def test_doi_forms_find_the_exact_record(quality_index):
    for value in ['doi:10.1109/JSSC.2020.3000001', 'https://doi.org/10.1109/JSSC.2020.3000001', 'DOI 10.1109/jssc.2020.3000001']:
        result = search({'q': value})
        assert numbers(result) == ['101'] and result['query']['doi'] == '10.1109/jssc.2020.3000001'
    assert numbers(top({'q': 'doi:10.1109/JSSC.2020.3000001'})) == ['101']


def test_top_k_ranks_names_and_whole_titles_first_with_reasons(quality_index):
    names = top({'q': 'Behzad Razavi', 'k': '5'})
    assert names['items'][0]['number'] == '111' and names['items'][0]['flags']['author_name']
    assert '113' not in numbers(names)  # the surname alone in an abstract does not match both words
    assert top({'q': 'Willy Sansen'})['items'][0]['number'] == '112'
    title = top({'q': 'The Design of Low-Jitter Fractional-N PLLs', 'k': '3'})
    assert title['items'][0]['number'] == '114' and title['items'][0]['flags']['exact_title']
    words = top({'q': 'design analog CMOS integrated circuits'})
    assert words['items'][0]['number'] == '111' and {r['field'] for r in words['items'][0]['reasons']} >= {'title'}
    sar = top({'q': 'SAR ADC', 'k': '10'})
    assert sar['total'] == 2 and len(sar['items']) == 2 and sar['view'] == 'top'
    alias = next(item for item in sar['items'] if item['number'] == '102')
    terms = [term for reason in alias['reasons'] for term in reason['terms']]
    assert any(term['alias'] and 'Successive-Approximation ADC' in term['matched'] for term in terms)
    assert top({'q': 'SAR ADC', 'k': '1'})['items'][0]['position'] == 1


def test_all_matches_view_pages_every_result_with_an_exact_total(quality_index):
    first = search({'q': 'design', 'limit': '2', 'sort': 'year'})
    seen, page = numbers(first), first
    while page['next_cursor']:
        page = search({'q': 'design', 'limit': '2', 'sort': 'year', 'cursor': page['next_cursor']})
        seen += numbers(page)
    assert len(seen) == len(set(seen)) == first['total'] == search({'q': 'design', 'totals': 'only'})['total']
    assert top({'q': 'design', 'k': '2'})['total'] == first['total']
