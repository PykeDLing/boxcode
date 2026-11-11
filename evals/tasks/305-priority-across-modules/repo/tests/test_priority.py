from cli import run
from export import to_csv
from store import Store


def test_default_and_explicit_priority():
    store = Store()
    assert store.add("Buy milk")["priority"] == "normal"
    assert store.add("Pay rent", priority="high")["priority"] == "high"


def test_cli_add_and_list():
    store = Store()
    run(["add", "Buy milk", "--tag", "home", "--priority", "high"], store)
    run(["add", "Water plants"], store)
    assert run(["list"], store) == "  1 [ ] Buy milk #home !\n  2 [ ] Water plants"


def test_csv_has_priority_column():
    store = Store()
    store.add("Buy milk", priority="low")
    assert to_csv(store.all()) == "id,title,priority,done,tags\n1,Buy milk,low,no,\n"
