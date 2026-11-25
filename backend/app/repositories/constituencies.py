import json
from functools import lru_cache
from pathlib import Path
from typing import Any


class ConstituencyBoundaryError(RuntimeError):
    """Raised when cached constituency boundaries cannot be read safely."""


def load_constituencies(
    cache_dir: Path,
    *,
    district_id: str | None = None,
) -> dict[str, Any]:
    boundary_dir = cache_dir / "processed" / "boundaries"
    geojson_path = boundary_dir / "constituencies.geojson"
    manifest_path = boundary_dir / "constituencies_manifest.json"
    try:
        geojson_stat = geojson_path.stat()
        manifest_stat = manifest_path.stat()
        geojson, manifest = _read_constituency_documents(
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
        raise ConstituencyBoundaryError(
            f"Could not read cached constituency boundaries: {exc}"
        ) from exc

    if not isinstance(geojson, dict) or geojson.get("type") != "FeatureCollection":
        raise ConstituencyBoundaryError(
            "Cached constituency file is not a GeoJSON FeatureCollection."
        )
    features = geojson.get("features")
    expected_count = manifest.get("constituency_count")
    if (
        not isinstance(features, list)
        or expected_count != 234
        or len(features) != 234
    ):
        raise ConstituencyBoundaryError(
            f"Expected 234 Tamil Nadu constituencies; found {len(features or [])}."
        )

    by_district: dict[str, list[dict[str, str | int]]] = {}
    seen_ids: set[str] = set()
    for feature in features:
        properties = feature.get("properties", {})
        constituency_id = properties.get("constituency_id")
        constituency_name = properties.get("constituency_name")
        parent_district_id = properties.get("district_id")
        parent_district_name = properties.get("district_name")
        ac_number = properties.get("ac_number")
        if not all(
            (
                constituency_id,
                constituency_name,
                parent_district_id,
                parent_district_name,
                ac_number is not None,
            )
        ):
            raise ConstituencyBoundaryError(
                "A constituency is missing its ID, name, number, or parent district."
            )
        if str(constituency_id) in seen_ids:
            raise ConstituencyBoundaryError(
                f"Duplicate constituency ID: {constituency_id}."
            )
        seen_ids.add(str(constituency_id))
        by_district.setdefault(str(parent_district_id), []).append(
            {
                "constituency_id": str(constituency_id),
                "constituency_name": str(constituency_name),
                "ac_number": int(ac_number),
                "district_id": str(parent_district_id),
                "district_name": str(parent_district_name),
            }
        )

    if district_id is not None and district_id not in by_district:
        raise ConstituencyBoundaryError(
            f"No Tamil Nadu constituencies are mapped to district {district_id}."
        )
    selected_features = (
        [
            feature
            for feature in features
            if str(feature.get("properties", {}).get("district_id")) == district_id
        ]
        if district_id is not None
        else features
    )
    districts = [
        {
            "district_id": current_district_id,
            "district_name": entries[0]["district_name"],
            "constituency_count": len(entries),
        }
        for current_district_id, entries in sorted(
            by_district.items(),
            key=lambda item: str(item[1][0]["district_name"]).casefold(),
        )
    ]
    for entries in by_district.values():
        entries.sort(
            key=lambda item: (
                str(item["constituency_name"]).casefold(),
                int(item["ac_number"]),
            )
        )
    selected = (
        by_district[district_id]
        if district_id is not None
        else [
            item
            for entries in by_district.values()
            for item in entries
        ]
    )
    selected.sort(
        key=lambda item: (
            str(item["district_name"]).casefold(),
            str(item["constituency_name"]).casefold(),
            int(item["ac_number"]),
        )
    )
    return {
        "constituency_count": len(selected),
        "state_constituency_count": 234,
        "district_id": district_id,
        "source": manifest.get("source"),
        "source_reference": manifest.get("source_reference"),
        "license": manifest.get("license"),
        "delimitation_year": manifest.get("delimitation_year"),
        "district_assignment": manifest.get("district_assignment"),
        "district_overlap_below_80_percent": manifest.get(
            "district_overlap_below_80_percent", []
        ),
        "districts": districts,
        "constituencies": selected,
        "geojson": {
            "type": "FeatureCollection",
            "features": selected_features,
        },
    }


@lru_cache(maxsize=4)
def _read_constituency_documents(
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
