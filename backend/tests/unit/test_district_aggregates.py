import json

import pandas as pd
from shapely.geometry import box, mapping

from app.services.district_aggregates import cache_district_static_batches


def test_district_cache_retains_pre_fallback_manifest_shape(tmp_path) -> None:
    boundary_dir = tmp_path / "processed" / "boundaries"
    boundary_dir.mkdir(parents=True)
    boundary = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": mapping(box(0, 0, 1, 1)),
                "properties": {
                    "district_id": "test_district",
                    "district_name": "Test District",
                    "source": "test source",
                    "source_reference": "https://example.test/boundary",
                    "license": "test license",
                    "boundary_year": "2021",
                },
            }
        ],
    }
    (boundary_dir / "districts.geojson").write_text(
        json.dumps(boundary),
        encoding="utf-8",
    )
    grid_dir = tmp_path / "processed" / "grids"
    grid_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "centroid_lon": 0.25,
                "centroid_lat": 0.25,
                "lst_c": 36.0,
                "population_estimated_2025": 10.0,
                "population_valid": True,
            },
            {
                "centroid_lon": 0.75,
                "centroid_lat": 0.75,
                "lst_c": None,
                "population_estimated_2025": None,
                "population_valid": False,
            },
        ]
    ).to_csv(grid_dir / "tamil_nadu_1000m_2026.csv", index=False)

    result = cache_district_static_batches(
        cache_dir=tmp_path,
        season_year=2026,
        batch_size=1,
    )

    manifest_path = (
        tmp_path
        / "processed"
        / "districts"
        / "static_batches"
        / "test_district"
        / "manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert result["batches"][0]["districts"][0]["status"] == "created"
    assert "lst_coverage_percent" not in manifest
    assert "population_coverage_percent" not in manifest
    assert manifest["worldpop_population_2025"] == 10.0
    assert manifest["processing_version"] == "district-static-batch-v1"

    cached = cache_district_static_batches(
        cache_dir=tmp_path,
        season_year=2026,
        batch_size=1,
    )
    assert cached["already_cached"] == 1
