"""English technical query understanding shared by metadata and full-text search.

Equivalent spellings of one concept may be expanded; related concepts are only
reported. Every rule is explicit so a match can always be explained."""
import re
import unicodedata
from urllib.parse import unquote

TOKEN = re.compile(r'[^\W_]+', re.UNICODE)
DOI = re.compile(r'^(?:doi\s*[:：]?\s*|(?:https?://)?(?:dx\.)?doi\.org/)?(10\.\d{4,9}/\S+)$', re.I)
XPLORE = re.compile(r'^(?:https?://)?ieeexplore\.ieee\.org/(?:abstract/)?document/(\d{1,64})/?(?:[?#].*)?$', re.I)
QUOTED = re.compile(r'"([^"]+)"|“([^”]+)”')

# Each concept lists unambiguous equivalent spellings. "abbreviations" expand to the
# spellings when typed, but are not added for other spellings because they have other
# meanings in IEEE literature. "related" concepts are suggestions, never matches.
CONCEPTS = [
    {'id': 'adc', 'label': 'ADC', 'forms': ['ADC', 'analog-to-digital converter', 'analogue-to-digital converter', 'A/D converter']},
    {'id': 'dac', 'label': 'DAC', 'forms': ['DAC', 'digital-to-analog converter', 'digital-to-analogue converter', 'D/A converter']},
    {'id': 'sar-adc', 'label': 'SAR ADC', 'forms': ['SAR ADC', 'successive approximation ADC', 'successive-approximation-register ADC',
     'successive approximation register ADC', 'SAR analog-to-digital converter', 'successive approximation analog-to-digital converter'],
     'related': ['noise-shaping SAR ADC', 'pipelined ADC', 'TI ADC']},
    {'id': 'ns-sar-adc', 'label': 'noise-shaping SAR ADC', 'forms': ['noise-shaping SAR ADC', 'NS-SAR ADC', 'NS SAR ADC', 'NSSAR ADC'], 'related': ['SAR ADC']},
    {'id': 'pipelined-adc', 'label': 'pipelined ADC', 'forms': ['pipelined ADC', 'pipeline ADC', 'pipelined analog-to-digital converter'], 'related': ['SAR ADC']},
    {'id': 'ti-adc', 'label': 'TI ADC', 'forms': ['TI ADC', 'TIADC', 'time-interleaved ADC', 'time-interleaved analog-to-digital converter'], 'related': ['SAR ADC']},
    {'id': 'delta-sigma', 'label': 'ΔΣ', 'forms': ['ΔΣ', 'ΣΔ', 'Δ-Σ', 'Σ-Δ', 'delta-sigma', 'sigma-delta']},
    {'id': 'delta-sigma-adc', 'label': 'ΔΣ ADC', 'forms': ['ΔΣ ADC', 'ΣΔ ADC', 'Δ-Σ ADC', 'Σ-Δ ADC', 'delta-sigma ADC', 'sigma-delta ADC', 'DSM ADC',
     'delta-sigma analog-to-digital converter', 'sigma-delta analog-to-digital converter'], 'related': ['ΔΣ modulator', 'CT ΔΣ modulator']},
    {'id': 'delta-sigma-modulator', 'label': 'ΔΣ modulator', 'forms': ['ΔΣ modulator', 'ΣΔ modulator', 'ΔΣM', 'ΣΔM', 'delta-sigma modulator', 'sigma-delta modulator'],
     'abbreviations': ['DSM'], 'related': ['ΔΣ ADC']},
    {'id': 'ct-delta-sigma', 'label': 'CT ΔΣ modulator', 'forms': ['CT ΔΣ modulator', 'CT ΣΔ modulator', 'CTDSM', 'CT-DSM', 'continuous-time ΔΣ modulator',
     'continuous-time ΣΔ modulator', 'continuous-time delta-sigma modulator', 'continuous-time sigma-delta modulator'], 'related': ['ΔΣ ADC']},
    {'id': 'pll', 'label': 'PLL', 'forms': ['PLL', 'phase-locked loop', 'phase-lock loop'], 'related': ['DLL', 'CDR', 'BBPLL', 'ADPLL', 'VCO']},
    {'id': 'bbpll', 'label': 'BBPLL', 'forms': ['BBPLL', 'BB-PLL', 'bang-bang PLL', 'bang-bang phase-locked loop'], 'related': ['BBPD', 'PLL', 'ADPLL']},
    {'id': 'bbpd', 'label': 'BBPD', 'forms': ['BBPD', 'BB-PD', 'bang-bang phase detector', 'bang-bang PD'], 'related': ['BBPLL', 'CDR']},
    {'id': 'adpll', 'label': 'ADPLL', 'forms': ['ADPLL', 'all-digital PLL', 'all-digital phase-locked loop'], 'related': ['PLL', 'DCO', 'TDC']},
    {'id': 'fractional-n-pll', 'label': 'fractional-N PLL', 'forms': ['fractional-N PLL', 'frac-N PLL', 'fractional-N phase-locked loop', 'fractional-N frequency synthesizer'], 'related': ['PLL', 'DTC']},
    {'id': 'cppll', 'label': 'charge-pump PLL', 'forms': ['charge-pump PLL', 'CPPLL', 'CP-PLL', 'charge-pump phase-locked loop'], 'related': ['PLL']},
    {'id': 'dll', 'label': 'DLL', 'forms': ['DLL', 'delay-locked loop', 'delay-lock loop'], 'related': ['PLL', 'MDLL']},
    {'id': 'mdll', 'label': 'MDLL', 'forms': ['MDLL', 'multiplying DLL', 'multiplying delay-locked loop'], 'related': ['DLL', 'PLL']},
    {'id': 'fll', 'label': 'FLL', 'forms': ['FLL', 'frequency-locked loop'], 'related': ['PLL']},
    {'id': 'cdr', 'label': 'CDR', 'forms': ['CDR', 'clock and data recovery', 'clock-and-data recovery', 'clock data recovery'], 'related': ['SerDes', 'PLL', 'BBPD']},
    {'id': 'serdes', 'label': 'SerDes', 'forms': ['SerDes', 'serializer/deserializer', 'serializer-deserializer'], 'related': ['CDR', 'transceiver']},
    {'id': 'vco', 'label': 'VCO', 'forms': ['VCO', 'voltage-controlled oscillator'], 'related': ['DCO', 'ring oscillator', 'PLL']},
    {'id': 'dco', 'label': 'DCO', 'forms': ['DCO', 'digitally controlled oscillator', 'digitally-controlled oscillator'], 'related': ['VCO', 'ADPLL']},
    {'id': 'ilo', 'label': 'ILO', 'forms': ['ILO', 'injection-locked oscillator'], 'related': ['VCO']},
    {'id': 'tdc', 'label': 'TDC', 'forms': ['TDC', 'time-to-digital converter'], 'related': ['DTC', 'ADPLL']},
    {'id': 'dtc', 'label': 'DTC', 'forms': ['DTC', 'digital-to-time converter'], 'related': ['TDC', 'fractional-N PLL']},
    {'id': 'lna', 'label': 'LNA', 'forms': ['LNA', 'low-noise amplifier']},
    {'id': 'tia', 'label': 'TIA', 'forms': ['TIA', 'transimpedance amplifier', 'trans-impedance amplifier']},
    {'id': 'ldo', 'label': 'LDO', 'forms': ['LDO', 'low-dropout regulator', 'low-dropout voltage regulator', 'low-dropout linear regulator']},
    {'id': 'opamp', 'label': 'op amp', 'forms': ['op amp', 'op-amp', 'opamp', 'operational amplifier'], 'related': ['OTA']},
    {'id': 'bandgap', 'label': 'bandgap reference', 'forms': ['bandgap reference', 'band-gap reference', 'bandgap voltage reference'], 'abbreviations': ['BGR']},
    {'id': 'cim', 'label': 'compute-in-memory', 'forms': ['compute-in-memory', 'computing-in-memory', 'in-memory computing', 'in-memory compute'],
     'abbreviations': ['CIM'], 'related': ['SRAM', 'processing-in-memory']},
]


def normalize(text):
    return unicodedata.normalize('NFKC', str(text or ''))


def fold(token):
    """Case folding with Latin diacritics removed, matching unicode61 remove_diacritics=2."""
    if token.isascii():
        return token.lower()
    return ''.join(c for c in unicodedata.normalize('NFKD', token) if not unicodedata.combining(c)).casefold()


def tokens(text):
    """The FTS5 unicode61 view of text: Unicode letters/numbers, case-folded."""
    return [fold(token) for token in TOKEN.findall(normalize(text))]


def spans(text):
    """Token boundaries in the original string, for highlighting without rewriting it."""
    return [(match.start(), match.end(), fold(match.group(0))) for match in TOKEN.finditer(text)]


PLURAL = re.compile(r'(?:converter|loop|oscillator|amplifier|regulator|detector|modulator|synthesizer|reference|amp|opamp|'
                    r'adc|dac|pll|dll|fll|mdll|bbpll|bbpd|adpll|cppll|cdr|vco|dco|ilo|tdc|dtc|lna|tia|ldo|bgr|ctdsm)$')


def _variants(form):
    words = tokens(form)
    if not words:
        return []
    values = [tuple(words)]
    # A plural is the same term; FTS5 indexes surface forms without stemming.
    if PLURAL.fullmatch(words[-1]):
        values.append(tuple(words[:-1] + [words[-1] + 's']))
    return values


def _compile():
    table = {}
    for concept in CONCEPTS:
        forms = []
        for form in concept['forms']:
            for variant in _variants(form):
                if variant not in forms:
                    forms.append(variant)
        abbreviations = [variant for form in concept.get('abbreviations', []) for variant in _variants(form)]
        compiled = {**concept, 'variants': forms, 'abbreviation_variants': abbreviations}
        for variant in forms + abbreviations:
            table.setdefault(variant, compiled)
    return table


VARIANTS = _compile()
LONGEST = max(len(key) for key in VARIANTS)


def normalize_doi(text):
    value = unquote(normalize(text).strip())
    match = DOI.match(value)
    if not match:
        return None
    doi = match.group(1).rstrip('.,;:"\'')
    while doi.endswith(')') and doi.count(')') > doi.count('('):
        doi = doi[:-1]
    return doi.lower()


def article_number(text):
    value = normalize(text).strip()
    if value.isdigit():
        return value
    match = XPLORE.match(value)
    return match.group(1) if match else None


def parse(query, terms='expand'):
    """Split a query into AND groups of alternative token sequences."""
    if terms not in ('expand', 'exact'):
        raise ValueError('Invalid term mode')
    text = normalize(query)
    groups = []
    for match in QUOTED.finditer(text):
        words = tokens(match.group(1) or match.group(2))
        if words:
            groups.append({'kind': 'phrase', 'text': ' '.join(words), 'alternatives': [tuple(words)]})
    words = tokens(QUOTED.sub(' ', text))
    index = 0
    while index < len(words):
        found = None
        for size in range(min(LONGEST, len(words) - index), 0, -1):
            key = tuple(words[index:index + size])
            if key in VARIANTS:
                found = (size, key, VARIANTS[key])
                break
        if found:
            size, key, concept = found
            typed = ' '.join(words[index:index + size])
            alternatives, spellings = [key], []
            if terms == 'expand':
                alternatives = list(concept['variants'])
                spellings = list(concept['forms'])
                if key in concept['abbreviation_variants']:
                    alternatives += [value for value in concept['abbreviation_variants'] if value not in alternatives]
                    spellings += concept.get('abbreviations', [])
            groups.append({'kind': 'concept', 'text': typed, 'concept': concept['id'], 'label': concept['label'],
                           'alternatives': alternatives, 'related': concept.get('related', []),
                           'equivalents': list({tuple(tokens(form)): form for form in reversed(spellings) if tuple(tokens(form)) != key}.values())[::-1]})
            index += size
        else:
            groups.append({'kind': 'word', 'text': words[index], 'alternatives': [(words[index],)]})
            index += 1
    return groups[:30]


def fts_expression(groups, field=None):
    if not groups:
        raise ValueError('Enter a searchable word')
    parts = []
    for group in groups:
        options = ['"' + ' '.join(alternative).replace('"', '""') + '"' for alternative in group['alternatives']]
        parts.append(options[0] if len(options) == 1 else '(' + ' OR '.join(options) + ')')
    expression = ' AND '.join(parts)
    return field + ':(' + expression + ')' if field else expression


def phrase_expression(words, field=None):
    expression = '"' + ' '.join(words).replace('"', '""') + '"'
    return field + ':' + expression if field else expression


def describe(groups):
    """Public explanation of how the query was interpreted."""
    result = []
    for group in groups:
        if group['kind'] == 'concept':
            result.append({'kind': 'concept', 'text': group['text'], 'label': group['label'],
                           'alternatives': [' '.join(value) for value in group['alternatives']],
                           'equivalents': group['equivalents'], 'related': group['related']})
        else:
            result.append({'kind': group['kind'], 'text': group['text']})
    return result


def locate(text, alternatives, words=None):
    """Character ranges of every alternative token sequence in text."""
    found = []
    words = spans(text) if words is None else words
    keys = [word[2] for word in words]
    for alternative in alternatives:
        size = len(alternative)
        for start in range(0, len(keys) - size + 1):
            if tuple(keys[start:start + size]) == alternative:
                found.append((words[start][0], words[start + size - 1][1], ' '.join(alternative)))
    return sorted(set(found))


def merge(ranges):
    result = []
    for start, end in sorted((start, end) for start, end, *_ in ranges):
        if result and start <= result[-1][1]:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([start, end])
    return result


def excerpt(text, ranges, width=260):
    """A window around the first match with highlight offsets relative to the excerpt."""
    ranges = merge(ranges)
    if not text:
        return {'text': '', 'highlights': []}
    if len(text) <= width or not ranges:
        start, end = 0, min(len(text), width)
    else:
        first = ranges[0][0]
        start = max(0, first - width // 3)
        end = min(len(text), start + width)
        start = max(0, end - width)
        if start:
            space = text.find(' ', start, first if first > start else start + 1)
            start = space + 1 if space != -1 else start
        if end < len(text):
            space = text.rfind(' ', max(start, ranges[0][1]), end)
            end = space if space > start else end
    prefix, suffix = ('…' if start else ''), ('…' if end < len(text) else '')
    highlights = [[s - start + len(prefix), e - start + len(prefix)] for s, e in ranges if s >= start and e <= end]
    return {'text': prefix + text[start:end] + suffix, 'highlights': highlights}
