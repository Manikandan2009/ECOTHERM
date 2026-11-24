import os
import time
import uuid
from pathlib import Path

import ee
import rasterio
import requests

from app.services.earth_engine import (
    EarthEngineClient,
    EarthEngineDataError,
)
from app.services.grid_processing import WORLDPOP_AGGREGATION_VERSION

EXPORT_GROUPS = {
    "landsat": 2,
    "sentinel": 6,
    "population": 4,
}
RASTER_BANDS = (
    "lst_c",
    "lst_valid_scenes",
    "ndvi",
    "ndvi_valid_scenes",
    "ndbi",
    "ndbi_valid_scenes",
    "ndwi",
    "ndwi_valid_scenes",
    "population_estimated_2025",
    "population_age_2020",
    "children_estimated_2020",
    "elderly_estimated_2020",
)


def export_summer_grid_geotiff(
    client: EarthEngineClient,
    region: ee.Geometry,
    *,
    region_id: str,
    year: int,
    resolution_m: int,
    output_path: Path,
) -> tuple[dict[str, int], dict[str, str]]:
    images, scene_counts = client.summer_grid_images(region, year, resolution_m)
    window = (
        f"{year}-04-01",
        f"{year}-06-30",
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_paths = {
        group: output_path.with_name(
            f".{output_path.stem}.{uuid.uuid4().hex}.{group}.tmp.tif"
        )
        for group in EXPORT_GROUPS
    }
    final_temporary_path = output_path.with_name(
        f".{output_path.stem}.{uuid.uuid4().hex}.tmp.tif"
    )
    try:
        for group, expected_bands in EXPORT_GROUPS.items():
            download_url = images[group].getDownloadURL(
                {
                    "name": f"ecotherm_{region_id}_{year}_{resolution_m}m_{group}",
                    "crs": "EPSG:32644",
                    "scale": resolution_m,
                    "region": region,
                    "format": "GEO_TIFF",
                    "filePerBand": False,
                }
            )
            response = _download_raster(download_url, group)
            if not response.ok:
                detail = response.text[:500].replace("\n", " ")
                raise EarthEngineDataError(
                    f"Earth Engine {group} raster download failed with HTTP "
                    f"{response.status_code}: {detail}"
                )
            temporary_paths[group].write_bytes(response.content)
            with rasterio.open(temporary_paths[group]) as dataset:
                if dataset.count != expected_bands or not dataset.width or not dataset.height:
                    raise EarthEngineDataError(
                        f"Earth Engine {group} raster has an unexpected band count "
                        "or empty dimensions."
                    )
                if dataset.crs is None or dataset.crs.to_epsg() != 32644:
                    raise EarthEngineDataError(
                        f"Earth Engine {group} raster did not use EPSG:32644."
                    )
        with rasterio.open(temporary_paths["landsat"]) as first:
            profile = first.profile.copy()
            profile.update(count=len(RASTER_BANDS), compress="deflate")
            with rasterio.open(final_temporary_path, "w", **profile) as output:
                band_number = 1
                for group in EXPORT_GROUPS:
                    with rasterio.open(temporary_paths[group]) as source:
                        if (
                            source.width != first.width
                            or source.height != first.height
                            or source.transform != first.transform
                            or source.crs != first.crs
                        ):
                            raise EarthEngineDataError(
                                "Earth Engine layer exports do not share an aligned grid."
                            )
                        for source_band in range(1, source.count + 1):
                            output.write(source.read(source_band), band_number)
                            output.set_band_description(
                                band_number,
                                RASTER_BANDS[band_number - 1],
                            )
                            band_number += 1
                output.update_tags(
                    worldpop_aggregation_version=(
                        WORLDPOP_AGGREGATION_VERSION
                        if resolution_m == 1000
                        else "native_100m_reprojection_v1"
                    )
                )
        os.replace(final_temporary_path, output_path)
    except EarthEngineDataError:
        raise
    except (ee.EEException, requests.RequestException) as exc:
        raise EarthEngineDataError(
            f"Could not export {region_id} at {resolution_m} m for summer {year}: {exc}"
        ) from exc
    except (OSError, rasterio.errors.RasterioError) as exc:
        raise EarthEngineDataError(
            f"Could not validate or cache Earth Engine raster: {exc}"
        ) from exc
    finally:
        cleanup_errors: list[str] = []
        for temporary_path in (*temporary_paths.values(), final_temporary_path):
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError as cleanup_error:
                cleanup_errors.append(
                    f"{temporary_path.name}: {cleanup_error}"
                )
        if cleanup_errors:
            raise EarthEngineDataError(
                "Could not remove temporary Earth Engine raster files: "
                + "; ".join(cleanup_errors)
            )

    return scene_counts, {
        "start_date": window[0],
        "end_date": window[1],
        "crs": "EPSG:32644",
        "nodata": "-9999",
        "download_bytes": str(output_path.stat().st_size),
        "band_names": ",".join(RASTER_BANDS),
    }


def _download_raster(url: str, group: str) -> requests.Response:
    last_error: requests.RequestException | None = None
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=(30, 300))
        except requests.RequestException as exc:
            last_error = exc
            if attempt == 2:
                raise EarthEngineDataError(
                    f"Could not download Earth Engine {group} raster after "
                    f"{attempt + 1} attempts: {exc}"
                ) from exc
            time.sleep(2**attempt)
            continue
        if response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
            time.sleep(2**attempt)
            continue
        return response
    raise EarthEngineDataError(
        f"Could not download Earth Engine {group} raster: {last_error}"
    )
