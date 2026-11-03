from text_utils import slugify


def test_simple():
    assert slugify("Hello World") == "hello-world"


def test_punctuation_runs():
    assert slugify("  Agents, Tools & MCP!! ") == "agents-tools-mcp"


def test_digits():
    assert slugify("Python 3.12 Release") == "python-3-12-release"


def test_empty():
    assert slugify("!!!") == ""
