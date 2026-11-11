from report import build_report

BASIC = [{'category': 'Food', 'amount': '12.50', 'date': '2026-01-05'},
 {'category': 'food ', 'amount': '7.25', 'date': '2026-02-11'},
 {'category': 'Travel', 'amount': '$1,234.50', 'date': '2026-01-20'},
 {'category': 'Books', 'amount': 30, 'date': '2026-02-01', 'note': 'gift'},
 {'category': 'Travel', 'amount': '(200.00)', 'date': '2026-02-28'}]


def test_text():
    assert build_report(BASIC) == (
        'SALES REPORT\n'
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
        'Largest: travel 1,234.50 in 2026-01\n'
    )


def test_csv():
    assert build_report(BASIC, "csv") == 'category,total,count\ntravel,1034.50,2\nbooks,30.00,1\nfood,19.75,2\nTOTAL,1084.25,5\n'


def test_empty():
    assert build_report([]) == "No data.\n"
