"""Compare exact minified ESM distributions; this is not an app bundle test."""

import gzip
import hashlib
import json
from pathlib import Path
import sys
import zlib


def describe(path: Path) -> dict[str, int | str]:
    data = path.read_bytes()
    return {"file": path.name, "raw_bytes": len(data), "gzip6_bytes": len(gzip.compress(data, compresslevel=6, mtime=0)), "sha256": hashlib.sha256(data).hexdigest()}


if __name__ == "__main__":
    paths = [Path(value) for value in sys.argv[1:]]
    if len(paths) != 2:
        raise SystemExit("usage: python -m scripts.spikes.engine_distribution_size PIXI_ESM PHASER_ESM")
    print(json.dumps({"zlib": zlib.ZLIB_VERSION, "files": [describe(path) for path in paths]}, sort_keys=True))
