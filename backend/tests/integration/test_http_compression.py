import httpx
import pytest

from app.api.v1 import map_layers as map_layer_routes
from app.main import app


@pytest.mark.asyncio
async def test_raster_tiles_are_not_gzipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        map_layer_routes,
        "render_lst_tile",
        lambda *args, **kwargs: b"x" * 2048,
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/v1/map/lst/0/0/0.png",
            headers={"accept-encoding": "gzip"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert "content-encoding" not in response.headers
    assert len(response.content) == 2048
