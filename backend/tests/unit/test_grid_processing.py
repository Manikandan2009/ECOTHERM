import numpy as np
from rasterio.crs import CRS
from rasterio.transform import Affine

from app.services.grid_processing import _legacy_worldpop_area_factors


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
