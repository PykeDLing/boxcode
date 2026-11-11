"""SKU codes.

Different systems write the same SKU in different ways: "ab-12", " AB 12 ", "ab_12", "AB--12", "-ab-12-".
normalize() maps every spelling of one product to a single canonical form: the parts in upper case,
joined by single hyphens, with nothing before the first part or after the last one.

Parts are separated by spaces, underscores and hyphens, in any number and any mix.
A code without any part (empty, or separators only) is invalid and raises ValueError.
"""


def normalize(code: str) -> str:
    cleaned = code.strip().upper().replace(" ", "-")
    if not cleaned:
        raise ValueError("empty SKU")
    return cleaned
