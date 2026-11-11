"""Freeze the local source and safely write inspectable study artifacts."""

import hashlib
import json
import subprocess
from pathlib import Path


def write_json(path: Path, value: dict) -> None:
    """Strict JSON prevents NaN from becoming a silently accepted scientific value."""
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def source_files(root: Path) -> list[Path]:
    """Select research inputs, excluding environments, Git internals and generated results."""
    files = {root / name for name in ("README.md", "LICENSE", "pyproject.toml", ".gitignore")}
    for directory in ("src", "tests", "docs", "experiments", ".github"):
        files.update(
            path
            for path in (root / directory).rglob("*")
            if path.is_file() and path.suffix in {".py", ".md", ".toml", ".yml", ".yaml"}
        )
    return sorted(path for path in files if path.is_file())


def git_output(root: Path, arguments: list[str]) -> str | None:
    """Git metadata is optional when running from an unpacked source distribution."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *arguments],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def archive_source(output: Path) -> dict:
    """Copy exact source bytes before any trial, including currently uncommitted work."""
    root = Path(__file__).resolve().parents[3]
    digests = {}
    for source in source_files(root):
        relative = source.relative_to(root)
        content = source.read_bytes()
        destination = output / "source" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        digests[relative.as_posix()] = hashlib.sha256(content).hexdigest()
    if not digests:
        raise RuntimeError("No source files available; run from the repository checkout")
    digest = hashlib.sha256(json.dumps(digests, sort_keys=True).encode()).hexdigest()
    write_json(output / "source-files.json", {"sha256": digest, "files": digests})
    return {
        "source_sha256": digest,
        "source_file_count": len(digests),
        "git_head": git_output(root, ["rev-parse", "HEAD"]),
        "git_status": git_output(root, ["status", "--porcelain"]),
    }


def verify_source_archive(directory: Path, expected_digest: str) -> None:
    """Check archived bytes independently of the current working tree."""
    inventory = json.loads((directory / "source-files.json").read_text(encoding="utf-8"))
    actual_digest = hashlib.sha256(
        json.dumps(inventory["files"], sort_keys=True).encode()
    ).hexdigest()
    if actual_digest != expected_digest or inventory["sha256"] != expected_digest:
        raise ValueError("source inventory digest mismatch")
    source_root = (directory / "source").resolve()
    for relative, expected in inventory["files"].items():
        path = (source_root / relative).resolve()
        if not path.is_relative_to(source_root):
            raise ValueError("source inventory path escapes archive")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"archived source changed: {relative}")
