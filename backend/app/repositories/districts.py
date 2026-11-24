import json
from pathlib import Path
from typing import Any


class DistrictBoundaryError(RuntimeError):
    """Raised when sourced district boundaries cannot be read safely."""


def load_district_boundaries(cache_dir: Path) -> dict[str, Any]:
    geojson_path = cache_dir / "processed" / "boundaries" / "districts.geojson"
    manifest_path = cache_dir / "processed" / "boundaries" / "districts_manifest.json"
    try:
        geojson = json.loads(geojson_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
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
