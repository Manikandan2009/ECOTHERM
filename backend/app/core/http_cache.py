import hashlib
from pathlib import Path

from fastapi import Request


def file_version_etag(paths: tuple[Path, ...], *, vary_by: str = "") -> str:
    parts = [vary_by]
    for path in paths:
        stat = path.stat()
        parts.append(
            f"{path.resolve()}:{stat.st_mtime_ns}:{stat.st_ctime_ns}:{stat.st_size}"
        )
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return f'W/"{digest}"'


def etag_matches(request: Request, etag: str) -> bool:
    candidates = request.headers.get("if-none-match", "")
    if not candidates:
        return False
    expected = etag.removeprefix("W/")
    return any(
        candidate.strip() == "*"
        or candidate.strip().removeprefix("W/") == expected
        for candidate in candidates.split(",")
    )
