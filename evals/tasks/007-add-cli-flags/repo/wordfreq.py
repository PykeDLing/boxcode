"""Word frequency report."""

import argparse
import collections
import re


def build_parser():
    parser = argparse.ArgumentParser(description="Count words in a text.")
    parser.add_argument("--text", required=True)
    return parser


def count_words(text):
    return collections.Counter(re.findall(r"[a-z']+", text.lower()))


def format_counts(counts):
    """One `word count` line per word: most frequent first, ties in alphabetical order."""
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return "\n".join(f"{word} {count}" for word, count in ordered)


def main(argv):
    """Return the report as a string."""
    args = build_parser().parse_args(argv)
    return format_counts(count_words(args.text))
