import json
from functools import lru_cache
from pathlib import Path
from typing import Any


class DistrictBoundaryError(RuntimeError):
    """Raised when sourced district boundaries cannot be read safely."""


def load_district_boundaries(cache_dir: Path) -> dict[str, Any]:
    geojson_path = cache_dir / "processed" / "boundaries" / "districts.geojson"
    manifest_path = cache_dir / "processed" / "boundaries" / "districts_manifest.json"
    try:
        geojson_stat = geojson_path.stat()
        manifest_stat = manifest_path.stat()
        geojson, manifest = _read_boundary_documents(
            str(geojson_path.resolve()),
            geojson_stat.st_mtime_ns,
            geojson_stat.st_ctime_ns,
            geojson_stat.st_size,
            str(manifest_path.resolve()),
            manifest_stat.st_mtime_ns,
            manifest_stat.st_ctime_ns,
            manifest_stat.st_size,
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise DistrictBoundaryError(
            f"Could not read cached district boundaries: {exc}"
        ) from exc

    if not isinstance(geojson, dict) or geojson.get("type") != "FeatureCollection":
        raise DistrictBoundaryError("Cached district file is not a valid FeatureCollection.")
    features = geojson.get("features")
    if not isinstance(features, list) or len(features) != 38:
        raise DistrictBoundaryError(
            f"Expected 38 Tamil Nadu district boundaries, found {len(features or [])}."
        )

    districts: list[dict[str, str]] = []
    for feature in features:
        properties = feature.get("properties", {})
        district_id = properties.get("district_id")
        district_name = properties.get("district_name")
        if not district_id or not district_name:
            raise DistrictBoundaryError(
                "A district boundary is missing district_id or district_name."
            )
        districts.append(
            {"district_id": str(district_id), "district_name": str(district_name)}
        )
    districts.sort(key=lambda item: item["district_name"])
    ids = [district["district_id"] for district in districts]
    if len(set(ids)) != len(ids):
        raise DistrictBoundaryError("District boundary IDs are not unique.")

    return {
        "district_count": len(districts),
        "boundary_year": manifest.get("boundary_year"),
        "source": manifest.get("boundary_source"),
        "license": manifest.get("boundary_license"),
        "selection_rule": manifest.get("selection_rule"),
        "districts": districts,
        "geojson": geojson,
    }


@lru_cache(maxsize=4)
def _read_boundary_documents(
    geojson_path: str,
    geojson_mtime_ns: int,
    geojson_ctime_ns: int,
    geojson_size: int,
    manifest_path: str,
    manifest_mtime_ns: int,
    manifest_ctime_ns: int,
    manifest_size: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    del (
        geojson_mtime_ns,
        geojson_ctime_ns,
        geojson_size,
        manifest_mtime_ns,
        manifest_ctime_ns,
        manifest_size,
    )
    return (
        json.loads(Path(geojson_path).read_text(encoding="utf-8")),
        json.loads(Path(manifest_path).read_text(encoding="utf-8")),
    )
