def reduce(samples, temporality):
    if temporality == "unknown" and len(samples) > 1:
        return None
    if temporality == "delta":
        return sum(samples)
    return samples[-1]


assert reduce([10, 2], "delta") == 12
assert reduce([10, 12], "cumulative") == 12
assert reduce([10, 12], "unknown") is None
print("PASS: delta, cumulative, and unknown ownership remain distinguishable")
