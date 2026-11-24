import json

import pytest

from app.repositories.districts import DistrictBoundaryError, load_district_boundaries


def test_load_district_boundaries_returns_38_sourced_polygons(tmp_path) -> None:
    cache_dir = tmp_path
    boundary_dir = cache_dir / "processed" / "boundaries"
    boundary_dir.mkdir(parents=True)
    features = [
        {
            "type": "Feature",
            "properties": {
                "district_id": f"district_{index}",
                "district_name": f"District {index}",
                "source": "Pathways Data Pvt. Ltd.",
                "license": "Open Data Commons Open Database License 1.0",
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[76, 8], [77, 8], [77, 9], [76, 8]]],
            },
        }
        for index in range(38)
    ]
    (boundary_dir / "districts.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": features}),
        encoding="utf-8",
    )
    (boundary_dir / "districts_manifest.json").write_text(
        json.dumps({
            "boundary_year": "2021",
            "boundary_source": "Pathways Data Pvt. Ltd.",
            "boundary_license": "Open Data Commons Open Database License 1.0",
            "selection_rule": "test boundary fixture",
        }),
        encoding="utf-8",
    )

    result = load_district_boundaries(cache_dir)

    assert result["district_count"] == 38
    assert len(result["districts"]) == 38
    assert result["source"] == "Pathways Data Pvt. Ltd."
    assert result["license"] == "Open Data Commons Open Database License 1.0"


def test_load_district_boundaries_rejects_wrong_count(tmp_path) -> None:
    boundary_dir = tmp_path / "processed" / "boundaries"
    boundary_dir.mkdir(parents=True)
    (boundary_dir / "districts.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": []}),
        encoding="utf-8",
    )
    (boundary_dir / "districts_manifest.json").write_text("{}", encoding="utf-8")

    with pytest.raises(DistrictBoundaryError, match="Expected 38"):
        load_district_boundaries(tmp_path)
