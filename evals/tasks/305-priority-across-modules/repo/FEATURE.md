# Feature: task priorities

Every task gets a priority: `"low"`, `"normal"` or `"high"`.

## Store (store.py)

1. Tasks returned by `add`, `get`, `all` and `complete` have a `"priority"` key. `Store.add(title, tags=(), priority="normal")`
   takes the priority of the new task.
2. Wherever a priority is given (in the store, in queries and on the command line) it is matched case-insensitively and
   stored in lower case: `"HIGH"` and `"High"` mean `"high"`. Nothing else is tolerated: surrounding whitespace
   (`" high"`), other words and values that are not strings (`None`, `2`) raise `ValueError("unknown priority: " + repr(value))`.
3. `Store.set_priority(task_id, priority)` changes the priority of a task and returns the updated task.
   An unknown id raises `KeyError`, like `get`.

## File format (store.py)

4. `dumps` writes `"version": 2` and every task includes its priority.
5. `loads` still reads version 1 files, which have no priorities: all their tasks become `"normal"`.
6. In a version 2 file every task must have a `"priority"` that is exactly one of the three lower-case names;
   a task without one, or with any other value (`"HIGH"` included), raises `ValueError`. Versions other than 1 and 2
   raise `ValueError` as before.

## Queries (query.py)

7. `filter_tasks(tasks, done=None, tag=None, priority=None, min_priority=None)`: `priority` keeps tasks with exactly
   that priority; `min_priority` keeps tasks with that priority or a higher one (`low` < `normal` < `high`).
   Filters that are given all apply together.
8. `sort_tasks(tasks, "priority")` puts `high` first, then `normal`, then `low`; tasks with the same priority stay in
   id order.

## Export (export.py)

9. `to_csv` gets a `priority` column between `title` and `done`: the header is `id,title,priority,done,tags`.

## Command line (cli.py)

10. `add TITLE --priority P` (short form `-p P`) sets the priority of the new task.
11. `list` accepts `--priority P`, `--min-priority P` and `--sort priority`, with the meaning of rules 7 and 8.
12. `list` marks priorities at the end of the line, after the tags: a high-priority task ends with ` !`, a low-priority
    task with ` (low)`, a normal one gets nothing. Example: `  1 [ ] Buy milk #home !`.
13. `priority ID P` changes the priority of a task and prints `priority of ID set to P` with the lower-case name,
    for example `priority of 3 set to high`. An unknown id raises `CliError("no such task: ID")`.
14. An invalid priority anywhere on the command line raises `CliError` with the message of rule 2, for example
    `unknown priority: 'urgent'`.
