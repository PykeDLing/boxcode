def slugify(title: str) -> str:
    """Turn a title into a URL slug.

    Lowercase ASCII letters and digits are kept, every other run of characters becomes a single "-",
    and there is no "-" at either end.
    """
    raise NotImplementedError
