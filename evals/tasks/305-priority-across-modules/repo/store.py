"""The task store and its file format.

A task is a dict: {"id": int, "title": str, "done": bool, "tags": sorted list of str}. The store hands out copies,
so changing a returned task does not change the store.
"""

import json

FORMAT_VERSION = 1


class Store:
    def __init__(self) -> None:
        self._tasks: dict[int, dict] = {}
        self._next_id = 1

    def add(self, title: str, tags=()) -> dict:
        title = title.strip()
        if not title:
            raise ValueError("title must not be empty")
        task = {"id": self._next_id, "title": title, "done": False, "tags": sorted(set(tags))}
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

    def all(self) -> list[dict]:
        """Every task, in id order."""
        return [_copy(self._tasks[task_id]) for task_id in sorted(self._tasks)]


def _copy(task: dict) -> dict:
    return {**task, "tags": list(task["tags"])}


def dumps(store: Store) -> str:
    return json.dumps({"version": FORMAT_VERSION, "next_id": store._next_id, "tasks": store.all()}, sort_keys=True)


def loads(text: str) -> Store:
    data = json.loads(text)
    if data.get("version") != FORMAT_VERSION:
        raise ValueError(f"unsupported version: {data.get('version')!r}")
    store = Store()
    for task in data["tasks"]:
        store._tasks[task["id"]] = {"id": task["id"], "title": task["title"], "done": task["done"],
                                    "tags": sorted(task["tags"])}
    store._next_id = data["next_id"]
    return store
