"""Command line front end. run(argv, store) executes one command against a store and returns what it prints.

    add TITLE [--tag TAG]...                       -> "added ID"
    list [--done | --open] [--tag TAG] [--sort KEY] -> one line per task, e.g. "  1 [x] Buy milk #home #shop"
    done ID                                        -> "completed ID"
    export                                         -> the CSV export

Anything wrong with the command raises CliError.
"""

import argparse

from export import to_csv
from query import filter_tasks, sort_tasks
from store import Store


class CliError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise CliError(message)


def _parser() -> _Parser:
    parser = _Parser(prog="todo", add_help=False)
    commands = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)
    add = commands.add_parser("add", add_help=False)
    add.add_argument("title")
    add.add_argument("--tag", action="append", default=[])
    listing = commands.add_parser("list", add_help=False)
    state = listing.add_mutually_exclusive_group()
    state.add_argument("--done", action="store_true")
    state.add_argument("--open", action="store_true")
    listing.add_argument("--tag")
    listing.add_argument("--sort", default="id")
    done = commands.add_parser("done", add_help=False)
    done.add_argument("id", type=int)
    commands.add_parser("export", add_help=False)
    return parser


def _line(task: dict) -> str:
    return f"{task['id']:>3} [{'x' if task['done'] else ' '}] {task['title']}" + "".join(f" #{tag}" for tag in task["tags"])


def run(argv: list[str], store: Store) -> str:
    args = _parser().parse_args(argv)
    if args.command == "add":
        try:
            task = store.add(args.title, args.tag)
        except ValueError as e:
            raise CliError(str(e)) from None
        return f"added {task['id']}"
    if args.command == "list":
        done = True if args.done else False if args.open else None
        try:
            tasks = sort_tasks(filter_tasks(store.all(), done=done, tag=args.tag), args.sort)
        except ValueError as e:
            raise CliError(str(e)) from None
        return "\n".join(_line(task) for task in tasks)
    if args.command == "done":
        try:
            store.complete(args.id)
        except KeyError:
            raise CliError(f"no such task: {args.id}") from None
        return f"completed {args.id}"
    return to_csv(store.all())
