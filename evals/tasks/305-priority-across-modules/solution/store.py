"""The task store and its file format.

A task is a dict: {"id": int, "title": str, "done": bool, "tags": sorted list of str, "priority": str}.
The store hands out copies, so changing a returned task does not change the store.
"""

import json

FORMAT_VERSION = 2
PRIORITIES = ("low", "normal", "high")


def normalize_priority(value) -> str:
    """The lower-case name of a priority given in any case; anything else is a ValueError."""
    if isinstance(value, str) and value.lower() in PRIORITIES:
        return value.lower()
    raise ValueError("unknown priority: " + repr(value))


class Store:
    def __init__(self) -> None:
        self._tasks: dict[int, dict] = {}
        self._next_id = 1

    def add(self, title: str, tags=(), priority="normal") -> dict:
        title = title.strip()
        if not title:
            raise ValueError("title must not be empty")
        task = {"id": self._next_id, "title": title, "done": False, "tags": sorted(set(tags)),
                "priority": normalize_priority(priority)}
        self._tasks[task["id"]] = task
        self._next_id += 1
        return _copy(task)

    def get(self, task_id: int) -> dict:
        if task_id not in self._tasks:
            raise KeyError(task_id)
        return _copy(self._tasks[task_id])

    def complete(self, task_id: int) -> dict:
        if task_id not in self._tasks:
            raise KeyError(task_id)
        self._tasks[task_id]["done"] = True
        return _copy(self._tasks[task_id])

    def set_priority(self, task_id: int, priority) -> dict:
        if task_id not in self._tasks:
            raise KeyError(task_id)
        self._tasks[task_id]["priority"] = normalize_priority(priority)
        return _copy(self._tasks[task_id])

    def all(self) -> list[dict]:
        """Every task, in id order."""
        return [_copy(self._tasks[task_id]) for task_id in sorted(self._tasks)]


def _copy(task: dict) -> dict:
    return {**task, "tags": list(task["tags"])}


def dumps(store: Store) -> str:
    return json.dumps({"version": FORMAT_VERSION, "next_id": store._next_id, "tasks": store.all()}, sort_keys=True)


def loads(text: str) -> Store:
    data = json.loads(text)
    version = data.get("version")
    if isinstance(version, bool) or version not in (1, 2):
        raise ValueError(f"unsupported version: {version!r}")
    store = Store()
    for task in data["tasks"]:
        if version == 1:
            priority = "normal"
        else:
            priority = task.get("priority")
            if not isinstance(priority, str) or priority not in PRIORITIES:
                raise ValueError(f"task {task['id']}: bad priority {priority!r}")
        store._tasks[task["id"]] = {"id": task["id"], "title": task["title"], "done": task["done"],
                                    "tags": sorted(task["tags"]), "priority": priority}
    store._next_id = data["next_id"]
    return store
