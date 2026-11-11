"""Filtering and sorting lists of tasks. Neither function changes its input."""


def filter_tasks(tasks: list[dict], done=None, tag=None) -> list[dict]:
    """Keep the tasks that match every filter that is not None."""
    result = []
    for task in tasks:
        if done is not None and task["done"] != done:
            continue
        if tag is not None and tag not in task["tags"]:
            continue
        result.append(task)
    return result


def sort_tasks(tasks: list[dict], key: str = "id") -> list[dict]:
    """Sort by "id" or by "title" (ignoring case; equal titles stay in id order)."""
    if key == "id":
        return sorted(tasks, key=lambda task: task["id"])
    if key == "title":
        return sorted(tasks, key=lambda task: (task["title"].lower(), task["id"]))
    raise ValueError(f"unknown sort key: {key!r}")
