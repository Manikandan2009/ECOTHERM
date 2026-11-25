import json

import httpx
import pytest

from app.api.v1 import constituencies as constituency_routes
from app.api.v1 import districts as district_routes
from app.core.settings import Settings
from app.main import app


def _write_boundary_cache(cache_dir) -> None:
    boundary_dir = cache_dir / "processed" / "boundaries"
    boundary_dir.mkdir(parents=True)
    districts = [
        {
            "type": "Feature",
            "properties": {
                "district_id": f"district_{index}",
                "district_name": f"District {index}",
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]],
            },
        }
        for index in range(38)
    ]
    constituencies = [
        {
            "type": "Feature",
            "properties": {
                "constituency_id": f"ac_{index:03d}",
                "constituency_name": f"Constituency {index}",
                "district_id": f"district_{index % 38}",
                "district_name": f"District {index % 38}",
                "ac_number": index + 1,
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]],
            },
        }
        for index in range(234)
    ]
    (boundary_dir / "districts.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": districts}),
        encoding="utf-8",
    )
    (boundary_dir / "districts_manifest.json").write_text(
        json.dumps({
            "boundary_year": 2026,
            "boundary_source": "test fixture",
            "boundary_license": "test license",
            "selection_rule": "test selection",
        }),
        encoding="utf-8",
    )
    (boundary_dir / "constituencies.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": constituencies}),
        encoding="utf-8",
    )
    (boundary_dir / "constituencies_manifest.json").write_text(
        json.dumps({
            "constituency_count": 234,
            "source": "test fixture",
            "source_reference": "test reference",
            "license": "test license",
            "delimitation_year": 2021,
            "district_assignment": "test assignment",
        }),
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_boundary_endpoints_support_gzip_and_conditional_requests(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_boundary_cache(tmp_path)
    settings = Settings(cache_dir=tmp_path)
    monkeypatch.setattr(district_routes, "get_settings", lambda: settings)
    monkeypatch.setattr(constituency_routes, "get_settings", lambda: settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        for endpoint in ("/api/v1/districts", "/api/v1/constituencies"):
            response = await client.get(
                endpoint,
                headers={"accept-encoding": "gzip"},
            )
            assert response.status_code == 200
            assert response.headers["content-encoding"] == "gzip"
            assert response.headers["cache-control"] == "public, max-age=300"
            assert response.headers["etag"].startswith('W/"')
            assert len(response.json()["geojson"]["features"]) in (38, 234)

            cached = await client.get(
                endpoint,
                headers={"if-none-match": response.headers["etag"]},
            )
            assert cached.status_code == 304
            assert cached.headers["etag"] == response.headers["etag"]

            if endpoint == "/api/v1/districts":
                manifest_path = (
                    tmp_path
                    / "processed"
                    / "boundaries"
                    / "districts_manifest.json"
                )
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["boundary_year"] = 2027
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                updated = await client.get(
                    endpoint,
                    headers={"if-none-match": response.headers["etag"]},
                )
                assert updated.status_code == 200
                assert updated.headers["etag"] != response.headers["etag"]
                assert updated.json()["boundary_year"] == 2027
