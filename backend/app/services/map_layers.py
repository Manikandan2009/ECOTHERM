import struct
import zlib
from functools import lru_cache
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject


TILE_SIZE = 256
WEB_MERCATOR_LIMIT = 20037508.342789244
MAX_NATIVE_ZOOM = 13
LAYER_BANDS = {
    "lst": 1,
    "ndvi": 3,
    "ndbi": 5,
    "ndwi": 7,
}
LAYER_RANGES = {
    "lst": (25.0, 55.0),
    "ndvi": (-1.0, 1.0),
    "ndbi": (-1.0, 1.0),
    "ndwi": (-1.0, 1.0),
}
LAYER_PALETTES = {
    "lst": ([52, 211, 153], [250, 204, 21], [249, 115, 22], [239, 68, 68]),
    "ndvi": ([145, 83, 55], [224, 190, 103], [173, 206, 120], [36, 132, 83]),
    "ndbi": ([52, 132, 89], [190, 196, 146], [221, 143, 93], [174, 53, 61]),
    "ndwi": ([155, 94, 58], [222, 194, 131], [125, 190, 204], [36, 104, 173]),
}


class MapLayerError(RuntimeError):
    """Raised when a cached map layer cannot be rendered."""


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    content = kind + data
    return (
        struct.pack(">I", len(data))
        + content
        + struct.pack(">I", zlib.crc32(content) & 0xFFFFFFFF)
    )


def _encode_png(rgba: np.ndarray) -> bytes:
    height, width, _ = rgba.shape
    scanlines = b"".join(
        b"\x00" + rgba[row].tobytes()
        for row in range(height)
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">2I5B", width, height, 8, 6, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(scanlines))
        + _png_chunk(b"IEND", b"")
    )


def _colourize_layer(values: np.ndarray, layer: str) -> np.ndarray:
    rgba = np.zeros((*values.shape, 4), dtype=np.uint8)
    if layer not in LAYER_PALETTES:
        raise MapLayerError(f"Unknown satellite layer: {layer}.")
    valid = np.isfinite(values)
    if layer == "lst":
        valid &= (values >= 0) & (values <= 80)
    else:
        valid &= (values >= -1) & (values <= 1)
    if not valid.any():
        return rgba

    minimum, maximum = LAYER_RANGES[layer]
    scale = np.clip((values[valid] - minimum) / (maximum - minimum), 0.0, 1.0)
    stops = np.array([0.0, 0.35, 0.68, 1.0])
    palette = np.array(LAYER_PALETTES[layer], dtype=np.float64)
    for channel in range(3):
        rgba[..., channel][valid] = np.interp(
            scale,
            stops,
            palette[:, channel],
        ).astype(np.uint8)
    rgba[..., 3][valid] = 170
    return rgba


@lru_cache(maxsize=128)
def _render_cached_tile(
    raster_path: str,
    modified_ns: int,
    layer: str,
    zoom: int,
    x: int,
    y: int,
) -> bytes:
    del modified_ns
    band = LAYER_BANDS.get(layer)
    if band is None:
        raise MapLayerError(f"Unknown satellite layer: {layer}.")
    if not 0 <= zoom <= MAX_NATIVE_ZOOM:
        raise MapLayerError(
            f"Satellite layer tiles are available through zoom {MAX_NATIVE_ZOOM}."
        )
    tile_count = 1 << zoom
    if not 0 <= x < tile_count or not 0 <= y < tile_count:
        raise MapLayerError("Tile coordinates are outside the valid map extent.")

    resolution = 2 * WEB_MERCATOR_LIMIT / (TILE_SIZE * tile_count)
    left = -WEB_MERCATOR_LIMIT + x * TILE_SIZE * resolution
    top = WEB_MERCATOR_LIMIT - y * TILE_SIZE * resolution
    tile_transform = from_origin(left, top, resolution, resolution)
    values = np.full((TILE_SIZE, TILE_SIZE), np.nan, dtype=np.float32)
    try:
        with rasterio.open(raster_path) as dataset:
            if dataset.count < band or dataset.crs is None:
                raise MapLayerError(
                    f"Cached satellite raster has no {layer.upper()} band or CRS."
                )
            reproject(
                source=rasterio.band(dataset, band),
                destination=values,
                src_transform=dataset.transform,
                src_crs=dataset.crs,
                src_nodata=dataset.nodata,
                dst_transform=tile_transform,
                dst_crs="EPSG:3857",
                dst_nodata=np.nan,
                resampling=Resampling.nearest,
            )
    except MapLayerError:
        raise
    except (OSError, rasterio.errors.RasterioError, ValueError) as exc:
        raise MapLayerError(f"Could not render cached satellite {layer.upper()}: {exc}") from exc
    return _encode_png(_colourize_layer(values, layer))


def render_satellite_tile(
    cache_dir: Path,
    *,
    layer: str,
    zoom: int,
    x: int,
    y: int,
    season_year: int = 2026,
) -> bytes:
    raster_path = (
        cache_dir
        / "raw"
        / "earth_engine"
        / f"tamil_nadu_{season_year}_1000m.tif"
    )
    if not raster_path.is_file():
        raise MapLayerError("Cached statewide satellite raster is unavailable.")
    try:
        modified_ns = raster_path.stat().st_mtime_ns
    except OSError as exc:
        raise MapLayerError(f"Could not inspect cached satellite raster: {exc}") from exc
    return _render_cached_tile(
        str(raster_path),
        modified_ns,
        layer,
        zoom,
        x,
        y,
    )


def render_lst_tile(
    cache_dir: Path,
    *,
    zoom: int,
    x: int,
    y: int,
    season_year: int = 2026,
) -> bytes:
    return render_satellite_tile(
        cache_dir,
        layer="lst",
        zoom=zoom,
        x=x,
        y=y,
        season_year=season_year,
    )
