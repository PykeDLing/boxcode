"""Filtering and sorting lists of tasks. Neither function changes its input."""

from store import PRIORITIES, normalize_priority


def filter_tasks(tasks: list[dict], done=None, tag=None, priority=None, min_priority=None) -> list[dict]:
    """Keep the tasks that match every filter that is not None."""
    if priority is not None:
        priority = normalize_priority(priority)
    if min_priority is not None:
        min_priority = normalize_priority(min_priority)
    result = []
    for task in tasks:
        if done is not None and task["done"] != done:
            continue
        if tag is not None and tag not in task["tags"]:
            continue
        if priority is not None and task["priority"] != priority:
            continue
        if min_priority is not None and PRIORITIES.index(task["priority"]) < PRIORITIES.index(min_priority):
            continue
        result.append(task)
    return result


def sort_tasks(tasks: list[dict], key: str = "id") -> list[dict]:
    """Sort by "id", by "title" (ignoring case) or by "priority" (high first); ties stay in id order."""
    if key == "id":
        return sorted(tasks, key=lambda task: task["id"])
    if key == "title":
        return sorted(tasks, key=lambda task: (task["title"].lower(), task["id"]))
    if key == "priority":
        return sorted(tasks, key=lambda task: (-PRIORITIES.index(task["priority"]), task["id"]))
    raise ValueError(f"unknown sort key: {key!r}")
