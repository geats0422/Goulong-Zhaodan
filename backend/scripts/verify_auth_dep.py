"""goulong-auth 本地依赖完整性校验 — CI 集成用"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

CHECKSUM_FILE = Path(__file__).resolve().parents[2] / "goulong-auth.sha256"
AUTH_PACKAGE = Path(__file__).resolve().parents[3] / "goulong-auth"


def compute_tree_hash(root: Path) -> str:
    if not root.is_dir():
        return ""
    hashes = []
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in str(path):
            continue
        rel = path.relative_to(root)
        content = path.read_bytes()
        h = hashlib.sha256(content).hexdigest()
        hashes.append(f"{h}  {rel}")
    combined = "\n".join(hashes)
    return hashlib.sha256(combined.encode()).hexdigest()


def snapshot() -> None:
    digest = compute_tree_hash(AUTH_PACKAGE)
    CHECKSUM_FILE.write_text(digest + "\n")
    print(f"snapshot: {digest}")


def verify() -> None:
    if not CHECKSUM_FILE.exists():
        print(f"SKIP: {CHECKSUM_FILE} not found (run `python -m scripts.verify_auth_dep snapshot` first)")
        sys.exit(0)
    expected = CHECKSUM_FILE.read_text().strip()
    actual = compute_tree_hash(AUTH_PACKAGE)
    if actual != expected:
        print(f"FAIL: goulong-auth hash mismatch\n  expected: {expected}\n  actual:   {actual}")
        sys.exit(1)
    print(f"OK: {actual}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "snapshot":
        snapshot()
    else:
        verify()
