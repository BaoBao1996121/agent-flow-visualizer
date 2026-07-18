# ruff: noqa: E701, E702 -- T4 requires this disposable spike to stay under 20 code lines.
from pathlib import Path
from subprocess import check_output
from tempfile import TemporaryDirectory


def git(root, *args):
    return check_output(["git", "-C", str(root), *args])


def names(raw):
    return set(raw.decode().rstrip("\0").split("\0")[1::2])


with TemporaryDirectory() as raw:
    root = Path(raw); git(root, "init", "-q"); git(root, "config", "user.email", "s0@example.test"); git(root, "config", "user.name", "S0")
    for name in ("old.txt", "staged.txt", "work.txt"): (root / name).write_text("base", encoding="utf-8")
    git(root, "add", "."); git(root, "commit", "-qm", "base"); base = git(root, "rev-parse", "HEAD").decode().strip()
    git(root, "mv", "old.txt", "new.txt"); git(root, "commit", "-qm", "rename")
    (root / "staged.txt").write_text("staged", encoding="utf-8"); git(root, "add", "staged.txt"); (root / "work.txt").write_text("work", encoding="utf-8"); (root / "odd ; name.txt").write_text("new", encoding="utf-8")
    changed = names(git(root, "diff", base, "HEAD", "--name-status", "-z", "--no-renames", "--no-ext-diff")) | names(git(root, "diff", "--cached", "--name-status", "-z", "--no-renames", "--no-ext-diff")) | names(git(root, "diff", "--name-status", "-z", "--no-renames", "--no-ext-diff")) | set(git(root, "ls-files", "--others", "--exclude-standard", "-z").decode().rstrip("\0").split("\0"))
    assert changed == {"old.txt", "new.txt", "staged.txt", "work.txt", "odd ; name.txt"}; print("PASS", sorted(changed))
