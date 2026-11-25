import geopandas as gpd
import numpy as np
import pytest
from rasterio.crs import CRS
from rasterio.transform import Affine
from shapely.geometry import Point

from app.services.grid_processing import (
    _legacy_worldpop_area_factors,
    write_grid_geojson,
)


def test_legacy_worldpop_area_factors_use_physical_source_pixel_area() -> None:
    factors = _legacy_worldpop_area_factors(
        Affine(1000, 0, 400000, 0, -1000, 1500000),
        height=2,
        raster_crs=CRS.from_epsg(32644),
        target_resolution_m=1000,
    )

    assert factors.shape == (2,)
    assert np.all((factors > 110) & (factors < 130))
    assert factors[1] < factors[0]


def test_grid_geojson_contains_polygon_cells_and_grid_attributes(tmp_path) -> None:
    frame = gpd.GeoDataFrame(
        {"grid_id": ["tamil_nadu-1000-00001-00001"], "lst_c": [40.0]},
        geometry=[Point(80.2, 13.1)],
        crs="EPSG:4326",
    )
    output_path = tmp_path / "grid.geojson"

    write_grid_geojson(frame, output_path, resolution_m=1000)

    exported = gpd.read_file(output_path)
    assert len(exported) == 1
    assert exported.iloc[0]["grid_id"] == "tamil_nadu-1000-00001-00001"
    assert exported.geometry.iloc[0].geom_type == "Polygon"
    assert exported.to_crs("EPSG:32644").geometry.iloc[0].area == pytest.approx(
        1_000_000,
        rel=0.01,
    )
