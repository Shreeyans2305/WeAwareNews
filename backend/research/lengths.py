"""Shared server-side presentation limits; research depth is unchanged."""
LENGTHS = {
    'brief': {'label': 'Brief', 'minWords': 400, 'maxWords': 700, 'outputTokens': 4500},
    'standard': {'label': 'Standard', 'minWords': 800, 'maxWords': 1500, 'outputTokens': 6500},
    'detailed': {'label': 'Detailed', 'minWords': 1500, 'maxWords': 2400, 'outputTokens': 10000},
}


def length_settings(value='standard'):
    if value not in LENGTHS:
        raise ValueError('Unsupported report length')
    return LENGTHS[value]


def report_words(report):
    return sum(len(paragraph['text'].split()) for section in report['sections'] for paragraph in section['paragraphs'])
