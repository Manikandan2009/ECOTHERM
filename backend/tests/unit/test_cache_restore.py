import io
import tarfile

import pytest

from app.cache_restore import (
    _extract_cache_archive,
    _sha256_file,
    _verify_archive_checksum,
)


_REQUIRED_ENTRIES = {
    "data/cache/processed/ecotherm.sqlite": b"sqlite fixture",
    "data/cache/processed/boundaries/districts.geojson": b"{}",
    "data/cache/raw/earth_engine/tamil_nadu_2026_1000m.tif": b"tiff fixture",
}


def _write_archive(path, entries: dict[str, bytes]) -> None:
    with tarfile.open(path, mode="w:gz") as archive:
        for name, contents in entries.items():
            member = tarfile.TarInfo(name)
            member.size = len(contents)
            archive.addfile(member, io.BytesIO(contents))


def test_extract_cache_archive_restores_required_files_without_overwriting(
    tmp_path,
) -> None:
    archive_path = tmp_path / "cache.tar.gz"
    cache_dir = tmp_path / "data" / "cache"
    _write_archive(archive_path, _REQUIRED_ENTRIES)

    restored_count = _extract_cache_archive(archive_path, cache_dir)

    assert restored_count == 3
    for entry, contents in _REQUIRED_ENTRIES.items():
        relative = entry.removeprefix("data/cache/")
        assert (cache_dir / relative).read_bytes() == contents


def test_extract_cache_archive_rejects_traversal_before_writing(tmp_path) -> None:
    archive_path = tmp_path / "unsafe.tar.gz"
    cache_dir = tmp_path / "data" / "cache"
    entries = {
        **_REQUIRED_ENTRIES,
        "../outside.txt": b"must not be written",
    }
    _write_archive(archive_path, entries)

    with pytest.raises(ValueError, match="Unsafe cache archive path"):
        _extract_cache_archive(archive_path, cache_dir)

    assert not (tmp_path / "outside.txt").exists()
    assert not cache_dir.exists()


def test_extract_cache_archive_refuses_different_existing_files(tmp_path) -> None:
    archive_path = tmp_path / "cache.tar.gz"
    cache_dir = tmp_path / "data" / "cache"
    existing_db = cache_dir / "processed" / "ecotherm.sqlite"
    existing_db.parent.mkdir(parents=True)
    existing_db.write_bytes(b"existing cache")
    _write_archive(archive_path, _REQUIRED_ENTRIES)

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        _extract_cache_archive(archive_path, cache_dir)

    assert existing_db.read_bytes() == b"existing cache"
    assert not (cache_dir / "processed" / "boundaries" / "districts.geojson").exists()


def test_verify_archive_checksum_checks_digest(tmp_path) -> None:
    archive_path = tmp_path / "cache.tar.gz"
    _write_archive(archive_path, _REQUIRED_ENTRIES)
    expected = _sha256_file(archive_path)

    _verify_archive_checksum(archive_path, expected.upper())

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        _verify_archive_checksum(archive_path, "0" * 64)
