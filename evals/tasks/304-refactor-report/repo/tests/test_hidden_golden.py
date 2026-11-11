"""What the original report.py returned and raised. Imports are inside the tests so that this file can be
collected before the reporting package exists."""

import importlib
import json

import pytest

GOLDEN = {'basic': {'rows': [{'category': 'Food', 'amount': '12.50', 'date': '2026-01-05'},
                    {'category': 'food ', 'amount': '7.25', 'date': '2026-02-11'},
                    {'category': 'Travel', 'amount': '$1,234.50', 'date': '2026-01-20'},
                    {'category': 'Books', 'amount': 30, 'date': '2026-02-01', 'note': 'gift'},
                    {'category': 'Travel', 'amount': '(200.00)', 'date': '2026-02-28'}],
           'text': 'SALES REPORT\n'
                   '============\n'
                   '\n'
                   'travel        1,034.50  (2)\n'
                   'books            30.00  (1)\n'
                   'food             19.75  (2)\n'
                   '----------------------\n'
                   'TOTAL         1,084.25  (5)\n'
                   '\n'
                   'By month:\n'
                   '  2026-01      1,247.00\n'
                   '  2026-02       -162.75\n'
                   '\n'
                   'Largest: travel 1,234.50 in 2026-01\n',
           'csv': 'category,total,count\ntravel,1034.50,2\nbooks,30.00,1\nfood,19.75,2\nTOTAL,1084.25,5\n'},
 'ties_sorted_by_name': {'rows': [{'category': 'pears', 'amount': '5', 'date': '2026-03-14'},
                                  {'category': 'Apples', 'amount': '5', 'date': '2026-03-14'},
                                  {'category': 'figs', 'amount': '5', 'date': '2026-03-14'},
                                  {'category': 'zebra', 'amount': '9', 'date': '2026-03-14'}],
                         'text': 'SALES REPORT\n'
                                 '============\n'
                                 '\n'
                                 'zebra             9.00  (1)\n'
                                 'apples            5.00  (1)\n'
                                 'figs              5.00  (1)\n'
                                 'pears             5.00  (1)\n'
                                 '----------------------\n'
                                 'TOTAL            24.00  (4)\n'
                                 '\n'
                                 'By month:\n'
                                 '  2026-03         24.00\n'
                                 '\n'
                                 'Largest: zebra 9.00 in 2026-03\n',
                         'csv': 'category,total,count\n'
                                'zebra,9.00,1\n'
                                'apples,5.00,1\n'
                                'figs,5.00,1\n'
                                'pears,5.00,1\n'
                                'TOTAL,24.00,4\n'},
 'float_rounding': {'rows': [{'category': 'a', 'amount': '1.005', 'date': '2026-03-14'},
                             {'category': 'b', 'amount': '2.675', 'date': '2026-03-14'},
                             {'category': 'c', 'amount': '0.125', 'date': '2026-03-14'},
                             {'category': 'd', 'amount': '0.135', 'date': '2026-03-14'},
                             {'category': 'e', 'amount': 0.30000000000000004, 'date': '2026-03-14'},
                             {'category': 'f', 'amount': 5, 'date': '2026-03-14'},
                             {'category': 'g', 'amount': '1.115', 'date': '2026-03-14'},
                             {'category': 'h', 'amount': 2.5, 'date': '2026-03-14'}],
                    'text': 'SALES REPORT\n'
                            '============\n'
                            '\n'
                            'f                 5.00  (1)\n'
                            'b                 2.68  (1)\n'
                            'h                 2.50  (1)\n'
                            'g                 1.12  (1)\n'
                            'a                 1.00  (1)\n'
                            'e                 0.30  (1)\n'
                            'd                 0.14  (1)\n'
                            'c                 0.12  (1)\n'
                            '----------------------\n'
                            'TOTAL            12.86  (8)\n'
                            '\n'
                            'By month:\n'
                            '  2026-03         12.86\n'
                            '\n'
                            'Largest: f 5.00 in 2026-03\n',
                    'csv': 'category,total,count\n'
                           'f,5.00,1\n'
                           'b,2.68,1\n'
                           'h,2.50,1\n'
                           'g,1.12,1\n'
                           'a,1.00,1\n'
                           'e,0.30,1\n'
                           'd,0.14,1\n'
                           'c,0.12,1\n'
                           'TOTAL,12.86,8\n'},
 'zero_rows_skipped_before_date_check': {'rows': [{'category': 'x', 'amount': '0', 'date': 'not a date'},
                                                  {'category': 'x', 'amount': '0.004', 'date': ''},
                                                  {'category': 'x', 'amount': 0},
                                                  {'category': 'x', 'amount': '(0.00)', 'date': '2026-13-01'},
                                                  {'category': 'x', 'amount': '3', 'date': '2026-03-14'}],
                                         'text': 'SALES REPORT\n'
                                                 '============\n'
                                                 '\n'
                                                 'x                 3.00  (1)\n'
                                                 '----------------------\n'
                                                 'TOTAL             3.00  (1)\n'
                                                 '\n'
                                                 'By month:\n'
                                                 '  2026-03          3.00\n'
                                                 '\n'
                                                 'Largest: x 3.00 in 2026-03\n',
                                         'csv': 'category,total,count\nx,3.00,1\nTOTAL,3.00,1\n'},
 'category_normalised': {'rows': [{'category': '  Food ', 'amount': '1', 'date': '2026-03-14'},
                                  {'category': 'FOOD', 'amount': '2', 'date': '2026-03-14'},
                                  {'category': None, 'amount': '3', 'date': '2026-03-14'},
                                  {'amount': '4', 'date': '2026-03-14'},
                                  {'category': '   ', 'amount': '5', 'date': '2026-03-14'},
                                  {'category': 42, 'amount': '6', 'date': '2026-03-14'},
                                  {'category': 'Uncategorised', 'amount': '7', 'date': '2026-03-14'}],
                         'text': 'SALES REPORT\n'
                                 '============\n'
                                 '\n'
                                 'uncategorised         19.00  (4)\n'
                                 '42                     6.00  (1)\n'
                                 'food                   3.00  (2)\n'
                                 '---------------------------\n'
                                 'TOTAL                 28.00  (7)\n'
                                 '\n'
                                 'By month:\n'
                                 '  2026-03         28.00\n'
                                 '\n'
                                 'Largest: uncategorised 7.00 in 2026-03\n',
                         'csv': 'category,total,count\n'
                                'uncategorised,19.00,4\n'
                                '42,6.00,1\n'
                                'food,3.00,2\n'
                                'TOTAL,28.00,7\n'},
 'largest_first_seen_wins_ties': {'rows': [{'category': 'a', 'amount': '50', 'date': '2026-01-01'},
                                           {'category': 'b', 'amount': '(50)', 'date': '2026-02-01'},
                                           {'category': 'c', 'amount': '50', 'date': '2026-03-01'}],
                                  'text': 'SALES REPORT\n'
                                          '============\n'
                                          '\n'
                                          'a                50.00  (1)\n'
                                          'c                50.00  (1)\n'
                                          'b               -50.00  (1)\n'
                                          '----------------------\n'
                                          'TOTAL            50.00  (3)\n'
                                          '\n'
                                          'By month:\n'
                                          '  2026-01         50.00\n'
                                          '  2026-02        -50.00\n'
                                          '  2026-03         50.00\n'
                                          '\n'
                                          'Largest: a 50.00 in 2026-01\n',
                                  'csv': 'category,total,count\n'
                                         'a,50.00,1\n'
                                         'c,50.00,1\n'
                                         'b,-50.00,1\n'
                                         'TOTAL,50.00,3\n'},
 'largest_by_absolute_value': {'rows': [{'category': 'sales', 'amount': '100', 'date': '2026-01-01'},
                                        {'category': 'refunds', 'amount': '(250.75)', 'date': '2026-02-01'}],
                               'text': 'SALES REPORT\n'
                                       '============\n'
                                       '\n'
                                       'sales           100.00  (1)\n'
                                       'refunds        -250.75  (1)\n'
                                       '----------------------\n'
                                       'TOTAL          -150.75  (2)\n'
                                       '\n'
                                       'By month:\n'
                                       '  2026-01        100.00\n'
                                       '  2026-02       -250.75\n'
                                       '\n'
                                       'Largest: refunds -250.75 in 2026-02\n',
                               'csv': 'category,total,count\n'
                                      'sales,100.00,1\n'
                                      'refunds,-250.75,1\n'
                                      'TOTAL,-150.75,2\n'},
 'csv_quoting': {'rows': [{'category': 'Food, drink', 'amount': '10', 'date': '2026-03-14'},
                          {'category': 'the "big" one', 'amount': '20', 'date': '2026-03-14'},
                          {'category': 'plain', 'amount': '30', 'date': '2026-03-14'}],
                 'text': 'SALES REPORT\n'
                         '============\n'
                         '\n'
                         'plain                 30.00  (1)\n'
                         'the "big" one         20.00  (1)\n'
                         'food, drink           10.00  (1)\n'
                         '---------------------------\n'
                         'TOTAL                 60.00  (3)\n'
                         '\n'
                         'By month:\n'
                         '  2026-03         60.00\n'
                         '\n'
                         'Largest: plain 30.00 in 2026-03\n',
                 'csv': 'category,total,count\n'
                        'plain,30.00,1\n'
                        '"the ""big"" one",20.00,1\n'
                        '"food, drink",10.00,1\n'
                        'TOTAL,60.00,3\n'},
 'wide_category': {'rows': [{'category': 'international shipping',
                             'amount': '1234567.89',
                             'date': '2026-03-14'},
                            {'category': 'misc', 'amount': '(0.01)', 'date': '2025-12-31'}],
                   'text': 'SALES REPORT\n'
                           '============\n'
                           '\n'
                           'international shipping  1,234,567.89  (1)\n'
                           'misc                           -0.01  (1)\n'
                           '------------------------------------\n'
                           'TOTAL                   1,234,567.88  (2)\n'
                           '\n'
                           'By month:\n'
                           '  2025-12         -0.01\n'
                           '  2026-03  1,234,567.89\n'
                           '\n'
                           'Largest: international shipping 1,234,567.89 in 2026-03\n',
                   'csv': 'category,total,count\n'
                          'international shipping,1234567.89,1\n'
                          'misc,-0.01,1\n'
                          'TOTAL,1234567.88,2\n'},
 'empty': {'rows': [], 'text': 'No data.\n', 'csv': 'category,total,count\nTOTAL,0.00,0\n'},
 'only_zero_rows': {'rows': [{'category': 'x', 'amount': '0', 'date': '2026-03-14'},
                             {'category': 'y', 'amount': 0.001, 'date': '2026-03-14'}],
                    'text': 'No data.\n',
                    'csv': 'category,total,count\nTOTAL,0.00,0\n'},
 'category_named_total': {'rows': [{'category': 'Total', 'amount': '1', 'date': '2026-03-14'},
                                   {'category': 'TOTAL', 'amount': '2', 'date': '2026-03-14'}],
                          'text': 'SALES REPORT\n'
                                  '============\n'
                                  '\n'
                                  'total             3.00  (2)\n'
                                  '----------------------\n'
                                  'TOTAL             3.00  (2)\n'
                                  '\n'
                                  'By month:\n'
                                  '  2026-03          3.00\n'
                                  '\n'
                                  'Largest: total 2.00 in 2026-03\n',
                          'csv': 'category,total,count\ntotal,3.00,2\nTOTAL,3.00,2\n'},
 'negative_total_sorts_last': {'rows': [{'category': 'refunds', 'amount': '(30)', 'date': '2026-03-14'},
                                        {'category': 'sales', 'amount': '10', 'date': '2026-03-14'},
                                        {'category': 'zero sum', 'amount': '5', 'date': '2026-03-14'},
                                        {'category': 'zero sum', 'amount': '(5)', 'date': '2026-03-14'}],
                               'text': 'SALES REPORT\n'
                                       '============\n'
                                       '\n'
                                       'sales            10.00  (1)\n'
                                       'zero sum          0.00  (2)\n'
                                       'refunds         -30.00  (1)\n'
                                       '----------------------\n'
                                       'TOTAL           -20.00  (4)\n'
                                       '\n'
                                       'By month:\n'
                                       '  2026-03        -20.00\n'
                                       '\n'
                                       'Largest: refunds -30.00 in 2026-03\n',
                               'csv': 'category,total,count\n'
                                      'sales,10.00,1\n'
                                      'zero sum,0.00,2\n'
                                      'refunds,-30.00,1\n'
                                      'TOTAL,-20.00,4\n'},
 'amount_spellings': {'rows': [{'category': 'a', 'amount': ' $ 1,000 ', 'date': '2026-03-14'},
                               {'category': 'a', 'amount': '-12.5', 'date': '2026-03-14'},
                               {'category': 'a', 'amount': '(-3)', 'date': '2026-03-14'},
                               {'category': 'a', 'amount': '1e2', 'date': '2026-03-14'},
                               {'category': 'a', 'amount': True, 'date': '2026-03-14'},
                               {'category': 'a', 'amount': '+4', 'date': '2026-03-14'}],
                      'text': 'SALES REPORT\n'
                              '============\n'
                              '\n'
                              'a             1,095.50  (6)\n'
                              '----------------------\n'
                              'TOTAL         1,095.50  (6)\n'
                              '\n'
                              'By month:\n'
                              '  2026-03      1,095.50\n'
                              '\n'
                              'Largest: a 1,000.00 in 2026-03\n',
                      'csv': 'category,total,count\na,1095.50,6\nTOTAL,1095.50,6\n'},
 'months_sorted': {'rows': [{'category': 'a', 'amount': '1', 'date': '2026-11-30'},
                            {'category': 'a', 'amount': '2', 'date': '2025-02-01'},
                            {'category': 'a', 'amount': '3', 'date': '2026-02-31'},
                            {'category': 'a', 'amount': '4', 'date': '2026-11-01'}],
                   'text': 'SALES REPORT\n'
                           '============\n'
                           '\n'
                           'a                10.00  (4)\n'
                           '----------------------\n'
                           'TOTAL            10.00  (4)\n'
                           '\n'
                           'By month:\n'
                           '  2025-02          2.00\n'
                           '  2026-02          3.00\n'
                           '  2026-11          5.00\n'
                           '\n'
                           'Largest: a 4.00 in 2026-11\n',
                   'csv': 'category,total,count\na,10.00,4\nTOTAL,10.00,4\n'}}

ERRORS = {'missing_amount_counts_skipped_rows': {'rows': [{'amount': 0}, {'category': 'x', 'date': '2026-03-14'}],
                                        'fmt': 'text',
                                        'message': 'row 2: missing amount'},
 'bad_amount': {'rows': [{'amount': 'abc', 'date': '2026-03-14'}],
                'fmt': 'text',
                'message': "row 1: bad amount 'abc'"},
 'bad_amount_empty': {'rows': [{'amount': '', 'date': '2026-03-14'}],
                      'fmt': 'csv',
                      'message': "row 1: bad amount ''"},
 'bad_amount_shown_as_given': {'rows': [{'amount': '1', 'date': '2026-03-14'},
                                        {'amount': ' $12x ', 'date': '2026-03-14'}],
                               'fmt': 'text',
                               'message': "row 2: bad amount ' $12x '"},
 'bad_date': {'rows': [{'amount': '1', 'date': '14/03/2026'}],
              'fmt': 'text',
              'message': "row 1: bad date '14/03/2026'"},
 'bad_date_month_13': {'rows': [{'amount': '1', 'date': '2026-13-01'}],
                       'fmt': 'text',
                       'message': "row 1: bad date '2026-13-01'"},
 'bad_date_month_00': {'rows': [{'amount': '1', 'date': '2026-00-10'}],
                       'fmt': 'text',
                       'message': "row 1: bad date '2026-00-10'"},
 'bad_date_missing': {'rows': [{'amount': '1'}], 'fmt': 'csv', 'message': "row 1: bad date ''"},
 'bad_date_letters': {'rows': [{'amount': '1', 'date': '2026-0a-01'}],
                      'fmt': 'text',
                      'message': "row 1: bad date '2026-0a-01'"},
 'first_bad_row_wins': {'rows': [{'amount': '1', 'date': '2026-03-14'}, {'amount': 'x'}, {}],
                        'fmt': 'text',
                        'message': "row 2: bad amount 'x'"},
 'amount_checked_before_date': {'rows': [{'amount': 'x', 'date': 'nope'}],
                                'fmt': 'text',
                                'message': "row 1: bad amount 'x'"},
 'unknown_format': {'rows': [{'category': 'Food', 'amount': '12.50', 'date': '2026-01-05'},
                             {'category': 'food ', 'amount': '7.25', 'date': '2026-02-11'},
                             {'category': 'Travel', 'amount': '$1,234.50', 'date': '2026-01-20'},
                             {'category': 'Books', 'amount': 30, 'date': '2026-02-01', 'note': 'gift'},
                             {'category': 'Travel', 'amount': '(200.00)', 'date': '2026-02-28'}],
                    'fmt': 'xml',
                    'message': 'unknown format: xml'},
 'unknown_format_empty_rows': {'rows': [], 'fmt': 'xml', 'message': 'unknown format: xml'},
 'row_error_before_format_error': {'rows': [{}], 'fmt': 'xml', 'message': 'row 1: missing amount'},
 'date_error_before_format_error': {'rows': [{'amount': '1', 'date': 'bad'}],
                                    'fmt': 'pdf',
                                    'message': "row 1: bad date 'bad'"},
 'format_is_case_sensitive': {'rows': [{'category': 'Food', 'amount': '12.50', 'date': '2026-01-05'},
                                       {'category': 'food ', 'amount': '7.25', 'date': '2026-02-11'},
                                       {'category': 'Travel', 'amount': '$1,234.50', 'date': '2026-01-20'},
                                       {'category': 'Books',
                                        'amount': 30,
                                        'date': '2026-02-01',
                                        'note': 'gift'},
                                       {'category': 'Travel', 'amount': '(200.00)', 'date': '2026-02-28'}],
                              'fmt': 'CSV',
                              'message': 'unknown format: CSV'}}

ENTRY_POINTS = ["report", "reporting"]


@pytest.mark.parametrize("module", ENTRY_POINTS)
@pytest.mark.parametrize("name", sorted(GOLDEN))
def test_text_output_unchanged(name, module):
    build_report = importlib.import_module(module).build_report
    case = GOLDEN[name]
    assert build_report(case["rows"]) == case["text"]
    assert build_report(case["rows"], "text") == case["text"]


@pytest.mark.parametrize("module", ENTRY_POINTS)
@pytest.mark.parametrize("name", sorted(GOLDEN))
def test_csv_output_unchanged(name, module):
    build_report = importlib.import_module(module).build_report
    case = GOLDEN[name]
    assert build_report(case["rows"], "csv") == case["csv"]
    assert build_report(case["rows"], fmt="csv") == case["csv"]


@pytest.mark.parametrize("module", ENTRY_POINTS)
@pytest.mark.parametrize("name", sorted(ERRORS))
def test_errors_unchanged(name, module):
    build_report = importlib.import_module(module).build_report
    case = ERRORS[name]
    with pytest.raises(ValueError) as info:
        build_report(case["rows"], case["fmt"])
    assert str(info.value) == case["message"]


@pytest.mark.parametrize("name", sorted(GOLDEN))
def test_steps_compose(name):
    parse_rows = importlib.import_module("reporting.parsing").parse_rows
    summarize = importlib.import_module("reporting.aggregate").summarize
    render = importlib.import_module("reporting.render")
    case = GOLDEN[name]
    summary = summarize(parse_rows(case["rows"]))
    assert isinstance(summary, dict)
    assert json.loads(json.dumps(summary)) == summary
    assert render.render_text(summary) == case["text"]
    assert render.render_csv(summary) == case["csv"]


def test_parse_rows_records():
    parse_rows = importlib.import_module("reporting.parsing").parse_rows
    rows = GOLDEN["zero_rows_skipped_before_date_check"]["rows"] + GOLDEN["category_normalised"]["rows"]
    assert parse_rows(rows) == [
        {"category": "x", "cents": 300, "month": "2026-03"},
        {"category": "food", "cents": 100, "month": "2026-03"},
        {"category": "food", "cents": 200, "month": "2026-03"},
        {"category": "uncategorised", "cents": 300, "month": "2026-03"},
        {"category": "uncategorised", "cents": 400, "month": "2026-03"},
        {"category": "uncategorised", "cents": 500, "month": "2026-03"},
        {"category": "42", "cents": 600, "month": "2026-03"},
        {"category": "uncategorised", "cents": 700, "month": "2026-03"},
    ]
    assert parse_rows([]) == []


@pytest.mark.parametrize("name", ["missing_amount_counts_skipped_rows", "bad_amount", "bad_date", "first_bad_row_wins"])
def test_parse_rows_raises_row_errors(name):
    parse_rows = importlib.import_module("reporting.parsing").parse_rows
    with pytest.raises(ValueError) as info:
        parse_rows(ERRORS[name]["rows"])
    assert str(info.value) == ERRORS[name]["message"]
