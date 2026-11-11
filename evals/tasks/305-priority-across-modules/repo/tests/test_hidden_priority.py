import json

import pytest

from cli import CliError, run
from export import to_csv
from query import filter_tasks, sort_tasks
from store import Store, dumps, loads


def sample():
    store = Store()
    store.add("Buy milk", ["shop", "home"], priority="high")  # 1
    store.add("call mum")  # 2 normal
    store.add("Book flights", ["travel"], "low")  # 3
    store.add("Pay rent", priority="high")  # 4
    store.add("Water plants", ["home"], priority="low")  # 5
    store.complete(2)
    return store


# rule 1
def test_every_accessor_returns_priority():
    store = Store()
    assert store.add("a") == {"id": 1, "title": "a", "done": False, "tags": [], "priority": "normal"}
    assert store.add("b", ["x"], "low") == {"id": 2, "title": "b", "done": False, "tags": ["x"], "priority": "low"}
    assert store.get(2)["priority"] == "low"
    assert store.complete(2) == {"id": 2, "title": "b", "done": True, "tags": ["x"], "priority": "low"}
    assert [task["priority"] for task in store.all()] == ["normal", "low"]


# rule 2
@pytest.mark.parametrize(("given", "stored"), [("HIGH", "high"), ("High", "high"), ("LOW", "low"), ("nOrMaL", "normal")])
def test_store_priority_is_case_insensitive(given, stored):
    store = Store()
    assert store.add("a", priority=given)["priority"] == stored
    assert store.set_priority(1, given)["priority"] == stored
    assert store.get(1)["priority"] == stored


@pytest.mark.parametrize("bad", [" high", "high ", "urgent", "", "medium", "1", None, 2, ["high"], True])
def test_store_rejects_unknown_priority(bad):
    store = Store()
    with pytest.raises(ValueError) as info:
        store.add("a", priority=bad)
    assert str(info.value) == "unknown priority: " + repr(bad)
    assert store.all() == []
    store.add("a")
    with pytest.raises(ValueError) as info:
        store.set_priority(1, bad)
    assert str(info.value) == "unknown priority: " + repr(bad)
    assert store.get(1)["priority"] == "normal"


# rule 3
def test_set_priority():
    store = sample()
    assert store.set_priority(2, "high") == {"id": 2, "title": "call mum", "done": True, "tags": [], "priority": "high"}
    assert store.get(2)["priority"] == "high"
    with pytest.raises(KeyError):
        store.set_priority(99, "high")


# rule 4
def test_dumps_writes_version_2_with_priorities():
    data = json.loads(dumps(sample()))
    assert data["version"] == 2 and data["next_id"] == 6
    assert [task["priority"] for task in data["tasks"]] == ["high", "normal", "low", "high", "low"]


def test_round_trip_keeps_priorities():
    store = loads(dumps(sample()))
    assert store.all() == sample().all()
    assert store.add("next", priority="LOW") == {"id": 6, "title": "next", "done": False, "tags": [], "priority": "low"}


# rule 5
def test_version_1_files_load_as_normal():
    old = json.dumps({"version": 1, "next_id": 3, "tasks": [
        {"id": 1, "title": "Buy milk", "done": False, "tags": ["home"]},
        {"id": 2, "title": "call mum", "done": True, "tags": []},
    ]})
    store = loads(old)
    assert store.all() == [
        {"id": 1, "title": "Buy milk", "done": False, "tags": ["home"], "priority": "normal"},
        {"id": 2, "title": "call mum", "done": True, "tags": [], "priority": "normal"},
    ]
    assert json.loads(dumps(store))["version"] == 2
    assert store.set_priority(1, "high")["priority"] == "high"


# rule 6
def v2(priority_fields):
    tasks = [{"id": i + 1, "title": f"t{i + 1}", "done": False, "tags": [], **fields}
             for i, fields in enumerate(priority_fields)]
    return json.dumps({"version": 2, "next_id": len(tasks) + 1, "tasks": tasks})


def test_version_2_file_loads():
    store = loads(v2([{"priority": "low"}, {"priority": "high"}, {"priority": "normal"}]))
    assert [task["priority"] for task in store.all()] == ["low", "high", "normal"]


@pytest.mark.parametrize("fields", [{}, {"priority": "HIGH"}, {"priority": "urgent"}, {"priority": None},
                                    {"priority": 1}, {"priority": " low"}, {"priority": ""}])
def test_version_2_file_with_bad_priority(fields):
    with pytest.raises(ValueError):
        loads(v2([{"priority": "low"}, fields]))


@pytest.mark.parametrize("version", [0, 3, "2", None])
def test_other_versions_rejected(version):
    with pytest.raises(ValueError):
        loads(json.dumps({"version": version, "next_id": 1, "tasks": []}))


# rule 7
def ids(tasks):
    return [task["id"] for task in tasks]


def test_filter_by_priority():
    tasks = sample().all()
    assert ids(filter_tasks(tasks, priority="high")) == [1, 4]
    assert ids(filter_tasks(tasks, priority="normal")) == [2]
    assert ids(filter_tasks(tasks, priority="LOW")) == [3, 5]


def test_filter_by_min_priority():
    tasks = sample().all()
    assert ids(filter_tasks(tasks, min_priority="low")) == [1, 2, 3, 4, 5]
    assert ids(filter_tasks(tasks, min_priority="normal")) == [1, 2, 4]
    assert ids(filter_tasks(tasks, min_priority="High")) == [1, 4]


def test_filters_combine():
    tasks = sample().all()
    assert ids(filter_tasks(tasks, done=False, min_priority="normal")) == [1, 4]
    assert ids(filter_tasks(tasks, tag="home", priority="low")) == [5]
    assert ids(filter_tasks(tasks, priority="low", min_priority="normal")) == []
    assert ids(filter_tasks(tasks, priority="high", min_priority="normal", tag="home", done=False)) == [1]
    assert ids(filter_tasks(tasks)) == [1, 2, 3, 4, 5]


@pytest.mark.parametrize("argument", ["priority", "min_priority"])
@pytest.mark.parametrize("bad", ["urgent", " high", 3])
def test_filter_rejects_unknown_priority(argument, bad):
    with pytest.raises(ValueError) as info:
        filter_tasks(sample().all(), **{argument: bad})
    assert str(info.value) == "unknown priority: " + repr(bad)


# rule 8
def test_sort_by_priority():
    tasks = sample().all()
    assert ids(sort_tasks(tasks, "priority")) == [1, 4, 2, 3, 5]
    assert ids(sort_tasks(list(reversed(tasks)), "priority")) == [1, 4, 2, 3, 5]
    assert ids(sort_tasks(tasks, "title")) == [3, 1, 2, 4, 5]
    assert ids(sort_tasks(list(reversed(tasks)))) == [1, 2, 3, 4, 5]
    with pytest.raises(ValueError):
        sort_tasks(tasks, "colour")


# rule 9
def test_csv_column_order():
    assert to_csv(sample().all()) == (
        "id,title,priority,done,tags\n"
        "1,Buy milk,high,no,home;shop\n"
        "2,call mum,normal,yes,\n"
        "3,Book flights,low,no,travel\n"
        "4,Pay rent,high,no,\n"
        "5,Water plants,low,no,home\n"
    )
    assert to_csv([]) == "id,title,priority,done,tags\n"


# rule 10
@pytest.mark.parametrize(("flags", "priority"), [
    ([], "normal"), (["--priority", "high"], "high"), (["-p", "low"], "low"), (["-p", "HIGH"], "high"),
    (["--tag", "x", "--priority", "Low", "--tag", "y"], "low"),
])
def test_cli_add(flags, priority):
    store = Store()
    assert run(["add", "Buy milk", *flags], store) == "added 1"
    assert store.get(1)["priority"] == priority


# rules 11 and 12
def test_cli_list_marks_priorities():
    assert run(["list"], sample()) == (
        "  1 [ ] Buy milk #home #shop !\n"
        "  2 [x] call mum\n"
        "  3 [ ] Book flights #travel (low)\n"
        "  4 [ ] Pay rent !\n"
        "  5 [ ] Water plants #home (low)"
    )


def test_cli_list_filters_and_sort():
    store = sample()
    assert run(["list", "--priority", "HIGH"], store) == "  1 [ ] Buy milk #home #shop !\n  4 [ ] Pay rent !"
    assert run(["list", "--min-priority", "normal", "--open"], store) == "  1 [ ] Buy milk #home #shop !\n  4 [ ] Pay rent !"
    assert run(["list", "--min-priority", "normal", "--done"], store) == "  2 [x] call mum"
    assert run(["list", "--tag", "home", "--priority", "low"], store) == "  5 [ ] Water plants #home (low)"
    assert run(["list", "--sort", "priority", "--tag", "home"], store) == (
        "  1 [ ] Buy milk #home #shop !\n  5 [ ] Water plants #home (low)")
    assert run(["list", "--sort", "priority"], store).splitlines()[2] == "  2 [x] call mum"
    assert run(["list", "--priority", "normal", "--open"], store) == ""


# rule 13
def test_cli_priority_command():
    store = sample()
    assert run(["priority", "3", "HIGH"], store) == "priority of 3 set to high"
    assert store.get(3)["priority"] == "high"
    assert run(["priority", "1", "normal"], store) == "priority of 1 set to normal"
    assert run(["list", "--priority", "high"], store) == "  3 [ ] Book flights #travel !\n  4 [ ] Pay rent !"
    with pytest.raises(CliError) as info:
        run(["priority", "42", "low"], store)
    assert str(info.value) == "no such task: 42"


# rule 14
@pytest.mark.parametrize("argv", [
    ["add", "x", "--priority", "urgent"], ["add", "x", "-p", "urgent"], ["list", "--priority", "urgent"],
    ["list", "--min-priority", "urgent"], ["priority", "1", "urgent"],
])
def test_cli_rejects_unknown_priority(argv):
    store = sample()
    with pytest.raises(CliError) as info:
        run(argv, store)
    assert str(info.value) == "unknown priority: 'urgent'"
    assert store.all() == sample().all()


def test_existing_commands_still_work():
    store = sample()
    assert run(["done", "1"], store) == "completed 1"
    assert run(["export"], store).splitlines()[1] == "1,Buy milk,high,yes,home;shop"
    with pytest.raises(CliError):
        run(["list", "--done", "--open"], store)
    with pytest.raises(CliError, match="title must not be empty"):
        run(["add", "   "], store)
