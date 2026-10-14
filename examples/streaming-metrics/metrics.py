def summarize(values):
    """Return count and mean from one pass over a non-empty numeric iterable."""
    count = 0

    def counted_values():
        nonlocal count
        for value in values:
            count += 1
            yield value

    # Keep sum's numeric behavior while counting without buffering the input.
    total = sum(counted_values())
    if count == 0:
        raise ValueError("cannot summarize empty input")
    return {"count": count, "mean": total / count}
