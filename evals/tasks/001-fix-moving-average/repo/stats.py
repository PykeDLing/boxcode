def moving_average(values: list[float], window: int) -> list[float]:
    """Average of each full window of `window` consecutive values."""
    if window <= 0:
        raise ValueError("window must be positive")
    out = []
    for i in range(len(values) - window):
        out.append(sum(values[i : i + window]) / window)
    return out
