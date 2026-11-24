import json

import pytest

from app.repositories.constituencies import (
    ConstituencyBoundaryError,
    load_constituencies,
)


def _write_boundaries(cache_dir, *, count=234):
    boundary_dir = cache_dir / "processed" / "boundaries"
    boundary_dir.mkdir(parents=True)
    features = []
    for index in range(count):
        district_name = "Alpha" if index % 2 == 0 else "Beta"
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "constituency_id": f"ac_{index:03d}_seat",
                    "constituency_name": f"Seat {count - index:03d}",
                    "ac_number": index + 1,
                    "district_id": "alpha" if district_name == "Alpha" else "beta",
                    "district_name": district_name,
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[76, 8], [77, 8], [77, 9], [76, 8]]],
                },
            }
        )
    (boundary_dir / "constituencies.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": features}),
        encoding="utf-8",
    )
    (boundary_dir / "constituencies_manifest.json").write_text(
        json.dumps(
            {
                "constituency_count": 234,
                "source": "DataMeet",
                "source_reference": "https://github.com/datameet/maps",
                "license": "CC BY 4.0",
                "delimitation_year": "2008",
            }
        ),
        encoding="utf-8",
    )


def test_load_constituencies_returns_sorted_records_and_source_metadata(tmp_path):
    _write_boundaries(tmp_path)

    result = load_constituencies(tmp_path)

    assert result["constituency_count"] == 234
    assert result["source_reference"] == "https://github.com/datameet/maps"
    assert result["license"] == "CC BY 4.0"
    assert result["delimitation_year"] == "2008"
    assert [item["district_name"] for item in result["districts"]] == [
        "Alpha",
        "Beta",
    ]
    first_alpha = [
        item["constituency_name"]
        for item in result["constituencies"]
        if item["district_id"] == "alpha"
    ]
    assert first_alpha == sorted(first_alpha, key=str.casefold)
    assert len(result["geojson"]["features"]) == 234


def test_load_constituencies_filters_only_the_requested_district(tmp_path):
    _write_boundaries(tmp_path)

    result = load_constituencies(tmp_path, district_id="alpha")

    assert result["district_id"] == "alpha"
    assert result["constituency_count"] == 117
    assert all(item["district_id"] == "alpha" for item in result["constituencies"])
    assert all(
        feature["properties"]["district_id"] == "alpha"
        for feature in result["geojson"]["features"]
    )


def test_load_constituencies_rejects_an_incomplete_boundary_cache(tmp_path):
    _write_boundaries(tmp_path, count=233)

    with pytest.raises(ConstituencyBoundaryError, match="Expected 234"):
        load_constituencies(tmp_path)
