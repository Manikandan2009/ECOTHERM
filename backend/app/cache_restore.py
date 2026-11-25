import hashlib
import hmac
import os
import re
import shutil
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.core.settings import get_settings

_CHUNK_SIZE = 1024 * 1024
_MAX_ARCHIVE_BYTES = 2 * 1024 * 1024 * 1024
_MAX_EXPANDED_BYTES = 2 * 1024 * 1024 * 1024
_REQUIRED_CACHE_FILES = {
    PurePosixPath("processed/ecotherm.sqlite"),
    PurePosixPath("processed/boundaries/districts.geojson"),
    PurePosixPath("raw/earth_engine/tamil_nadu_2026_1000m.tif"),
}


def _validate_archive_url(url: str) -> None:
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "github.com"
        or parsed.username is not None
        or parsed.password is not None
        or not parsed.path.startswith(
            "/Manikandan2009/ECOTHERM/releases/download/"
        )
    ):
        raise ValueError("Cache archive URL must be a public ECOTHERM GitHub release URL.")


def _download_archive(url: str, destination: Path) -> None:
    request = Request(url, headers={"User-Agent": "ECOTHERM-cache-restore"})
    total_bytes = 0
    with urlopen(request, timeout=120) as response:
        final_url = urlparse(response.geturl())
        final_host = final_url.hostname or ""
        if final_url.scheme != "https" or not (
            final_host == "github.com"
            or final_host.endswith(".githubusercontent.com")
        ):
            raise ValueError("Cache archive download redirected to an untrusted host.")

        with destination.open("wb") as archive_file:
            while chunk := response.read(_CHUNK_SIZE):
                total_bytes += len(chunk)
                if total_bytes > _MAX_ARCHIVE_BYTES:
                    raise ValueError("Cache archive exceeds the 2 GiB download limit.")
                archive_file.write(chunk)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_archive_checksum(path: Path, expected_sha256: str) -> None:
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
        raise ValueError("ECOTHERM_CACHE_SHA256 must be a 64-character hexadecimal SHA-256.")

    actual_sha256 = _sha256_file(path)
    if not hmac.compare_digest(actual_sha256, expected_sha256.lower()):
        raise ValueError(
            "Cache archive SHA-256 mismatch: "
            f"expected {expected_sha256.lower()}, received {actual_sha256}."
        )


def _validated_members(
    members: list[tarfile.TarInfo],
) -> list[tuple[tarfile.TarInfo, PurePosixPath]]:
    validated: list[tuple[tarfile.TarInfo, PurePosixPath]] = []
    seen: set[tuple[str, ...]] = set()
    expanded_bytes = 0
    required_files: set[PurePosixPath] = set()

    for member in members:
        raw_name = member.name
        if not raw_name or "\\" in raw_name or "\x00" in raw_name:
            raise ValueError(f"Unsafe cache archive path: {raw_name!r}.")

        normalized_name = raw_name[:-1] if raw_name.endswith("/") else raw_name
        parts = normalized_name.split("/")
        if (
            raw_name.startswith("/")
            or any(part in {"", ".", ".."} for part in parts)
            or parts[:2] != ["data", "cache"]
        ):
            raise ValueError(f"Unsafe cache archive path: {raw_name!r}.")

        if member.issym() or member.islnk() or not (
            member.isfile() or member.isdir()
        ):
            raise ValueError(f"Unsupported cache archive entry: {raw_name!r}.")

        path_parts = tuple(parts)
        if path_parts in seen:
            raise ValueError(f"Duplicate cache archive path: {raw_name!r}.")
        seen.add(path_parts)

        relative_parts = parts[2:]
        relative_path = PurePosixPath(*relative_parts)
        if not relative_parts and not member.isdir():
            raise ValueError("The data/cache archive root must be a directory.")

        if member.isfile():
            if member.size < 0:
                raise ValueError(f"Invalid file size for cache entry {raw_name!r}.")
            expanded_bytes += member.size
            if expanded_bytes > _MAX_EXPANDED_BYTES:
                raise ValueError("Expanded cache exceeds the 2 GiB extraction limit.")
            required_files.add(relative_path)

        validated.append((member, relative_path))

    missing_files = _REQUIRED_CACHE_FILES - required_files
    if missing_files:
        missing = ", ".join(sorted(path.as_posix() for path in missing_files))
        raise ValueError(f"Cache archive is missing required files: {missing}.")

    return validated


def _extract_cache_archive(archive_path: Path, cache_dir: Path) -> int:
    with tarfile.open(archive_path, mode="r:gz") as archive:
        validated = _validated_members(archive.getmembers())

        with tempfile.TemporaryDirectory(prefix="ecotherm-cache-stage-") as temp_dir:
            staged_cache = Path(temp_dir) / "data" / "cache"
            staged_cache.mkdir(parents=True)

            for member, relative_path in validated:
                destination = staged_cache.joinpath(*relative_path.parts)
                if member.isdir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue

                destination.parent.mkdir(parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    raise ValueError(f"Unable to read cache archive entry {member.name!r}.")

                copied_bytes = 0
                with source, destination.open("xb") as output:
                    while chunk := source.read(_CHUNK_SIZE):
                        copied_bytes += len(chunk)
                        if copied_bytes > member.size:
                            raise ValueError(
                                f"Cache archive entry exceeded its declared size: {member.name!r}."
                            )
                        output.write(chunk)
                if copied_bytes != member.size:
                    raise ValueError(
                        f"Cache archive entry size mismatch: {member.name!r}."
                    )

            if cache_dir.is_symlink():
                raise ValueError(f"Cache directory must not be a symlink: {cache_dir}.")
            if cache_dir.exists() and not cache_dir.is_dir():
                raise ValueError(f"Cache path is not a directory: {cache_dir}.")

            staged_files = [
                path for path in staged_cache.rglob("*") if path.is_file()
            ]
            for staged_file in staged_files:
                relative_path = staged_file.relative_to(staged_cache)
                destination = cache_dir / relative_path
                current = cache_dir
                for part in relative_path.parts[:-1]:
                    current = current / part
                    if current.is_symlink():
                        raise ValueError(
                            f"Cache destination must not traverse a symlink: {current}."
                        )
                if destination.is_symlink():
                    raise ValueError(
                        f"Cache destination must not be a symlink: {destination}."
                    )
                if destination.exists():
                    if not destination.is_file() or _sha256_file(
                        destination
                    ) != _sha256_file(staged_file):
                        raise FileExistsError(
                            "Refusing to overwrite different cache data at "
                            f"{destination}."
                        )

            for staged_file in staged_files:
                relative_path = staged_file.relative_to(staged_cache)
                destination = cache_dir / relative_path
                if destination.exists():
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(staged_file, destination)

    return len(staged_files)


def main() -> None:
    archive_url = os.environ.get("ECOTHERM_CACHE_ARCHIVE_URL", "")
    expected_sha256 = os.environ.get("ECOTHERM_CACHE_SHA256", "")
    if not archive_url:
        raise ValueError("ECOTHERM_CACHE_ARCHIVE_URL is required for cache restoration.")
    if not expected_sha256:
        raise ValueError("ECOTHERM_CACHE_SHA256 is required for cache restoration.")
    _validate_archive_url(archive_url)

    with tempfile.TemporaryDirectory(prefix="ecotherm-cache-download-") as temp_dir:
        archive_path = Path(temp_dir) / "ecotherm-cache.tar.gz"
        _download_archive(archive_url, archive_path)
        _verify_archive_checksum(archive_path, expected_sha256)
        restored_files = _extract_cache_archive(
            archive_path,
            get_settings().cache_dir,
        )

    print(
        f"Restored and verified {restored_files} required cache assets "
        f"under {get_settings().cache_dir}."
    )


if __name__ == "__main__":
    main()
