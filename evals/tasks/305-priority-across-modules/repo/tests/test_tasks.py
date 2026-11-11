import pytest

from cli import CliError, run
from query import filter_tasks, sort_tasks
from store import Store, dumps, loads


def sample():
    store = Store()
    store.add("Buy milk", ["shop", "home"])
    store.add("call mum")
    store.add("Book flights", ["travel"])
    store.complete(2)
    return store


def test_store_round_trip():
    store = loads(dumps(sample()))
    assert [task["title"] for task in store.all()] == ["Buy milk", "call mum", "Book flights"]
    assert store.get(1)["tags"] == ["home", "shop"] and store.get(2)["done"] is True
    assert store.add("next")["id"] == 4


def test_filter_and_sort():
    tasks = sample().all()
    assert [task["id"] for task in filter_tasks(tasks, done=False)] == [1, 3]
    assert [task["id"] for task in filter_tasks(tasks, tag="travel")] == [3]
    assert [task["id"] for task in sort_tasks(tasks, "title")] == [3, 1, 2]


def test_cli_list_and_done():
    store = sample()
    assert run(["list", "--open"], store) == "  1 [ ] Buy milk #home #shop\n  3 [ ] Book flights #travel"
    assert run(["done", "3"], store) == "completed 3"
    assert run(["list", "--done", "--sort", "title"], store) == "  3 [x] Book flights #travel\n  2 [x] call mum"


def test_cli_errors():
    with pytest.raises(CliError, match="no such task: 9"):
        run(["done", "9"], Store())
    with pytest.raises(CliError):
        run(["list", "--sort", "colour"], Store())
