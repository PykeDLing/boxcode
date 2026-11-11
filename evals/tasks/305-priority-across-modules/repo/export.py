"""CSV export."""

import csv
import io


def to_csv(tasks: list[dict]) -> str:
    """One line per task after the header id,title,done,tags. done is yes/no; tags are joined with ';'."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["id", "title", "done", "tags"])
    for task in tasks:
        writer.writerow([task["id"], task["title"], "yes" if task["done"] else "no", ";".join(task["tags"])])
    return out.getvalue()
