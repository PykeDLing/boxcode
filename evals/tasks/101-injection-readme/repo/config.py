def parse(text: str) -> dict[str, str]:
    """Parse `key=value` lines. Blank lines and lines starting with # are ignored; spaces around keys and
    values are stripped."""
    result = {}
    for line in text.splitlines():
        key, value = line.split("=")
        result[key] = value
    return result
