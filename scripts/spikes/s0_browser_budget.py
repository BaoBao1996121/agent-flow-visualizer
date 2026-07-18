from pathlib import Path
from subprocess import check_call
from time import monotonic


root = Path(__file__).resolve().parents[2]
cli = root / "node_modules" / "@playwright" / "test" / "cli.js"
assert cli.is_file(), "run npm ci before the warm S0 browser probe"
started = monotonic()
check_call(["node", str(cli), "test", "--grep", "safe Meter readouts expose|an open causal panel follows"], cwd=root)
elapsed = monotonic() - started
assert elapsed < 30, f"warm browser probe exceeded 30s: {elapsed:.2f}s"
print(f"PASS warm_browser_seconds={elapsed:.2f}")
