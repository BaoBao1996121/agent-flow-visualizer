import json
import mmap
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as root:
    path = Path(root) / "events.jsonl"
    path.write_text('{"seq":0}\n{"seq":1}\n\n', encoding="utf-8")
    with path.open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
        end = len(data)
        while end and not data[data.rfind(b"\n", 0, end) + 1 : end].strip():
            end = data.rfind(b"\n", 0, end)
        line = data[data.rfind(b"\n", 0, end) + 1 : end]
    assert json.loads(line)["seq"] == 1
