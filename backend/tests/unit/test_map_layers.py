import struct
import zlib

import numpy as np
import rasterio

from app.services.map_layers import (
    TILE_SIZE,
    WEB_MERCATOR_LIMIT,
    render_lst_tile,
    render_satellite_tile,
)
from rasterio.transform import from_origin


def _first_png_pixel(image: bytes) -> tuple[int, int, int, int]:
    offset = 8
    compressed = bytearray()
    while offset < len(image):
        length = struct.unpack(">I", image[offset:offset + 4])[0]
        kind = image[offset + 4:offset + 8]
        data = image[offset + 8:offset + 8 + length]
        if kind == b"IDAT":
            compressed.extend(data)
        offset += length + 12
    decoded = zlib.decompress(compressed)
    return tuple(decoded[1:5])


def test_lst_tile_uses_discrete_raster_values_and_transparent_nodata(
    tmp_path,
) -> None:
    raster_dir = tmp_path / "raw" / "earth_engine"
    raster_dir.mkdir(parents=True)
    raster_path = raster_dir / "tamil_nadu_2026_1000m.tif"
    pixel_size = 2 * WEB_MERCATOR_LIMIT / TILE_SIZE
    values = np.full((TILE_SIZE, TILE_SIZE), 40.0, dtype=np.float32)
    with rasterio.open(
        raster_path,
        "w",
        driver="GTiff",
        width=TILE_SIZE,
        height=TILE_SIZE,
        count=1,
        dtype="float32",
        crs="EPSG:3857",
        transform=from_origin(-WEB_MERCATOR_LIMIT, WEB_MERCATOR_LIMIT, pixel_size, pixel_size),
        nodata=-9999,
    ) as dataset:
        dataset.write(values, 1)

    image = render_lst_tile(tmp_path, zoom=0, x=0, y=0)

    assert image.startswith(b"\x89PNG\r\n\x1a\n")
    assert struct.unpack(">2I", image[16:24]) == (TILE_SIZE, TILE_SIZE)
    red, green, blue, alpha = _first_png_pixel(image)
    assert alpha == 170
    assert red + green + blue > 0

    with rasterio.open(raster_path, "r+") as dataset:
        dataset.write(np.full_like(values, -9999), 1)
    transparent = render_lst_tile(tmp_path, zoom=0, x=0, y=0)
    assert _first_png_pixel(transparent)[3] == 0


def test_satellite_index_tiles_use_their_own_band_and_hide_nodata(tmp_path) -> None:
    raster_dir = tmp_path / "raw" / "earth_engine"
    raster_dir.mkdir(parents=True)
    raster_path = raster_dir / "tamil_nadu_2026_1000m.tif"
    pixel_size = 2 * WEB_MERCATOR_LIMIT / TILE_SIZE
    with rasterio.open(
        raster_path,
        "w",
        driver="GTiff",
        width=TILE_SIZE,
        height=TILE_SIZE,
        count=7,
        dtype="float32",
        crs="EPSG:3857",
        transform=from_origin(-WEB_MERCATOR_LIMIT, WEB_MERCATOR_LIMIT, pixel_size, pixel_size),
        nodata=-9999,
    ) as dataset:
        dataset.write(np.full((TILE_SIZE, TILE_SIZE), -9999, dtype=np.float32), 1)
        dataset.write(np.full((TILE_SIZE, TILE_SIZE), 0.6, dtype=np.float32), 3)
        dataset.write(np.full((TILE_SIZE, TILE_SIZE), -0.3, dtype=np.float32), 5)
        dataset.write(np.full((TILE_SIZE, TILE_SIZE), 0.8, dtype=np.float32), 7)

    tiles = {
        layer: render_satellite_tile(
            tmp_path,
            layer=layer,
            zoom=0,
            x=0,
            y=0,
        )
        for layer in ("ndvi", "ndbi", "ndwi")
    }

    pixels = {layer: _first_png_pixel(tile) for layer, tile in tiles.items()}
    assert all(pixel[3] == 170 for pixel in pixels.values())
    assert len({pixel[:3] for pixel in pixels.values()}) == 3

    transparent = render_satellite_tile(
        tmp_path,
        layer="lst",
        zoom=0,
        x=0,
        y=0,
    )
    assert _first_png_pixel(transparent)[3] == 0
