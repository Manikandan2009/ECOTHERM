from dataclasses import dataclass
from datetime import date

import ee
from google.auth.exceptions import GoogleAuthError


class EarthEngineError(RuntimeError):
    """Base error for Earth Engine initialization and data access."""


class EarthEngineInitializationError(EarthEngineError):
    """Raised when Earth Engine credentials or project access are unavailable."""


class EarthEngineDataError(EarthEngineError):
    """Raised when an Earth Engine collection request cannot be evaluated."""


@dataclass(frozen=True)
class DateWindow:
    start: date
    end_exclusive: date


def summer_window(year: int) -> DateWindow:
    if year < 2013 or year > 9998:
        raise ValueError("summer season year must be between 2013 and 9998")
    return DateWindow(start=date(year, 4, 1), end_exclusive=date(year, 7, 1))


class EarthEngineClient:
    LANDSAT_COLLECTIONS = (
        "LANDSAT/LC08/C02/T1_L2",
        "LANDSAT/LC09/C02/T1_L2",
    )
    SENTINEL_COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"
    LANDSAT_CLOUD_MASK_BITS = sum(1 << bit for bit in (0, 1, 2, 3, 4, 5))
    SENTINEL_SCL_MASK_CLASSES = (0, 1, 3, 7, 8, 9, 10, 11)
    WORLDPOP_POPULATION_COLLECTION = "WorldPop/GP/100m/R2025A/v1/pop"
    WORLDPOP_AGE_COLLECTION = "WorldPop/GP/100m/pop_age_sex_cons_unadj"

    def __init__(self, project_id: str) -> None:
        if not project_id.strip():
            raise ValueError("Earth Engine Cloud project ID must not be empty")
        self.project_id = project_id.strip()
        self._initialized = False

    def authenticate(self, force: bool = False) -> None:
        try:
            ee.Authenticate(force=force)
        except (ee.EEException, GoogleAuthError) as exc:
            raise EarthEngineInitializationError(
                "Earth Engine authentication failed. Complete Google's local "
                "authentication flow, then retry."
            ) from exc
        self.initialize()

    def initialize(self) -> None:
        try:
            ee.Initialize(project=self.project_id)
        except (ee.EEException, GoogleAuthError) as exc:
            raise EarthEngineInitializationError(
                f"Could not initialize Earth Engine with project "
                f"{self.project_id!r}. Run `python -m app.cli "
                "authenticate-earth-engine`, verify Earth Engine is enabled "
                "for the project, and confirm the signed-in account has access."
            ) from exc
        self._initialized = True

    def check_access(self) -> int:
        self.initialize()
        try:
            algorithms = ee.data.getAlgorithms()
        except (ee.EEException, GoogleAuthError) as exc:
            raise EarthEngineInitializationError(
                f"Earth Engine authenticated, but project {self.project_id!r} "
                "could not access the Earth Engine API. Verify project "
                "registration, billing/quota configuration, and account access."
            ) from exc
        return len(algorithms)

    def landsat_summer_collection(self, region: ee.Geometry, year: int) -> ee.ImageCollection:
        self._require_initialized()
        window = summer_window(year)
        collections = [
            ee.ImageCollection(collection_id)
            .filterBounds(region)
            .filterDate(window.start.isoformat(), window.end_exclusive.isoformat())
            .filter(ee.Filter.eq("PROCESSING_LEVEL", "L2SP"))
            .filter(ee.Filter.lt("CLOUD_COVER", 80))
            .map(
                lambda image: ee.Image(self._mask_and_scale_landsat(image)).clip(
                    region
                )
            )
            for collection_id in self.LANDSAT_COLLECTIONS
        ]
        return collections[0].merge(collections[1])

    def sentinel_summer_collection(
        self, region: ee.Geometry, year: int
    ) -> ee.ImageCollection:
        self._require_initialized()
        window = summer_window(year)
        return (
            ee.ImageCollection(self.SENTINEL_COLLECTION)
            .filterBounds(region)
            .filterDate(window.start.isoformat(), window.end_exclusive.isoformat())
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 80))
            .map(
                lambda image: ee.Image(
                    self._mask_and_derive_sentinel_indices(image)
                ).clip(region)
            )
        )

    def count_scenes(self, collection: ee.ImageCollection) -> int:
        self._require_initialized()
        try:
            count = collection.size().getInfo()
        except (ee.EEException, GoogleAuthError) as exc:
            raise EarthEngineDataError(
                f"Could not evaluate an Earth Engine collection with project "
                f"{self.project_id!r}. Check project access, quota, network, "
                "and the selected region/date window."
            ) from exc
        if not isinstance(count, int) or count < 0:
            raise EarthEngineDataError(
                "Earth Engine returned an invalid scene count."
            )
        return count

    def summer_grid_images(
        self,
        region: ee.Geometry,
        year: int,
        resolution_m: int,
    ) -> tuple[dict[str, ee.Image], dict[str, int]]:
        if resolution_m not in (100, 1000):
            raise ValueError("analysis resolution must be 100 m or 1000 m")
        landsat = self.landsat_summer_collection(region, year)
        sentinel = self.sentinel_summer_collection(region, year)
        scene_counts = {
            "landsat_scenes": self.count_scenes(landsat),
            "sentinel2_scenes": self.count_scenes(sentinel),
        }
        if not scene_counts["landsat_scenes"]:
            raise EarthEngineDataError(
                f"No Landsat L2SP scenes intersect the selected region in summer {year}."
            )
        if not scene_counts["sentinel2_scenes"]:
            raise EarthEngineDataError(
                f"No Sentinel-2 scenes intersect the selected region in summer {year}."
            )

        target_projection = ee.Projection("EPSG:32644").atScale(resolution_m)
        landsat_projection = ee.Image(landsat.first()).select("lst_c").projection()
        landsat_grid = self._seasonal_band_on_grid(
            landsat,
            "lst_c",
            "lst_valid_scenes",
            landsat_projection,
            target_projection,
        )
        sentinel_bands: list[ee.Image] = []
        for band in ("ndvi", "ndbi", "ndwi"):
            source_band = sentinel.select(band)
            source_projection = ee.Image(sentinel.first()).select(band).projection()
            sentinel_bands.append(
                ee.Image.cat(
                    [
                        source_band.median()
                        .setDefaultProjection(source_projection)
                        .resample("bilinear")
                        .reproject(target_projection)
                        .rename(band),
                        source_band.count()
                        .unmask(0)
                        .setDefaultProjection(source_projection)
                        .reproject(target_projection)
                        .rename(f"{band}_valid_scenes"),
                    ]
                )
            )
        sentinel_grid = ee.Image.cat(sentinel_bands)
        population_grid, population_counts = self.worldpop_grid_image(
            region,
            resolution_m,
        )
        scene_counts.update(population_counts)
        return {
            "landsat": landsat_grid.unmask(-9999),
            "sentinel": sentinel_grid.unmask(-9999),
            "population": population_grid.unmask(-9999),
        }, scene_counts

    def worldpop_grid_image(
        self,
        region: ee.Geometry,
        resolution_m: int,
    ) -> tuple[ee.Image, dict[str, int]]:
        if resolution_m not in (100, 1000):
            raise ValueError("analysis resolution must be 100 m or 1000 m")
        population, age_population, age_counts, population_counts = (
            self._worldpop_images(region)
        )
        target_projection = ee.Projection("EPSG:32644").atScale(resolution_m)
        if resolution_m == 1000:
            target_area = float(resolution_m**2)
            source_area = ee.Image.pixelArea().reproject(population.projection())
            area_ratio = ee.Image.constant(target_area).divide(source_area)
            population = (
                population.multiply(area_ratio)
                .setDefaultProjection(population.projection())
                .reduceResolution(
                    reducer=ee.Reducer.sum(),
                    bestEffort=False,
                    maxPixels=65535,
                )
                .reproject(target_projection)
            )
            age_counts = age_counts.setDefaultProjection(
                age_population.projection()
            )
            age_source = age_population.addBands(age_counts)
            source_area = ee.Image.pixelArea().reproject(
                age_population.projection()
            )
            area_ratio = ee.Image.constant(target_area).divide(source_area)
            age = (
                age_source.multiply(area_ratio)
                .setDefaultProjection(age_population.projection())
                .reduceResolution(
                    reducer=ee.Reducer.sum(),
                    bestEffort=False,
                    maxPixels=65535,
                )
                .reproject(target_projection)
            )
        else:
            population = population.reproject(target_projection)
            age = age_population.addBands(age_counts).reproject(target_projection)
        return population.addBands(age), population_counts

    @staticmethod
    def _seasonal_band_on_grid(
        collection: ee.ImageCollection,
        band: str,
        count_band: str,
        source_projection: ee.Projection,
        target_projection: ee.Projection,
    ) -> ee.Image:
        source = collection.select(band)
        composite = source.median().setDefaultProjection(source_projection)
        count = (
            source.count()
            .unmask(0)
            .setDefaultProjection(source_projection)
        )
        return ee.Image.cat(
            [
                composite.reduceResolution(
                    reducer=ee.Reducer.mean(),
                    bestEffort=False,
                    maxPixels=65535,
                )
                .reproject(target_projection)
                .rename(band),
                count.reduceResolution(
                    reducer=ee.Reducer.mean(),
                    bestEffort=False,
                    maxPixels=65535,
                )
                .reproject(target_projection)
                .rename(count_band),
            ]
        )

    def _worldpop_images(
        self,
        region: ee.Geometry,
    ) -> tuple[ee.Image, ee.Image, ee.Image, dict[str, int]]:
        self._require_initialized()
        population_collection = (
            ee.ImageCollection(self.WORLDPOP_POPULATION_COLLECTION)
            .filterBounds(region)
            .filter(ee.Filter.eq("country", "IND"))
            .filter(ee.Filter.eq("year", 2025))
        )
        age_collection = (
            ee.ImageCollection(self.WORLDPOP_AGE_COLLECTION)
            .filterBounds(region)
            .filter(ee.Filter.eq("country", "IND"))
            .filter(ee.Filter.eq("year", 2020))
        )
        counts = {
            "worldpop_population_2025_images": self.count_scenes(
                population_collection
            ),
            "worldpop_age_2020_images": self.count_scenes(age_collection),
        }
        if not counts["worldpop_population_2025_images"]:
            raise EarthEngineDataError(
                "WorldPop has no India population image for year 2025."
            )
        if not counts["worldpop_age_2020_images"]:
            raise EarthEngineDataError(
                "WorldPop has no India age/sex image for year 2020."
            )
        population = (
            ee.Image(population_collection.first())
            .select("population")
            .rename("population_estimated_2025")
            .clip(region)
        )
        age_source = ee.Image(age_collection.first()).clip(region)
        age_population = age_source.select("population").rename(
            "population_age_2020"
        )
        child_bands = [
            "M_0",
            "M_1",
            "M_5",
            "M_10",
            "F_0",
            "F_1",
            "F_5",
            "F_10",
        ]
        elderly_bands = [
            "M_65",
            "M_70",
            "M_75",
            "M_80",
            "F_65",
            "F_70",
            "F_75",
            "F_80",
        ]
        age_counts = ee.Image.cat(
            [
                age_source.select(child_bands)
                .reduce(ee.Reducer.sum())
                .rename("children_estimated_2020"),
                age_source.select(elderly_bands)
                .reduce(ee.Reducer.sum())
                .rename("elderly_estimated_2020"),
            ]
        )
        return population, age_population, age_counts, counts

    @staticmethod
    def _mask_and_scale_landsat(image: ee.Image) -> ee.Image:
        qa_pixel = image.select("QA_PIXEL")
        qa_radsat = image.select("QA_RADSAT")
        clear = qa_pixel.bitwiseAnd(EarthEngineClient.LANDSAT_CLOUD_MASK_BITS).eq(0)
        unsaturated = qa_radsat.eq(0)
        lst_celsius = (
            image.select("ST_B10")
            .multiply(0.00341802)
            .add(149.0)
            .subtract(273.15)
            .rename("lst_c")
        )
        return (
            lst_celsius.updateMask(clear)
            .updateMask(unsaturated)
            .copyProperties(image, ["system:time_start", "LANDSAT_PRODUCT_ID"])
        )

    @staticmethod
    def _mask_and_derive_sentinel_indices(image: ee.Image) -> ee.Image:
        scl = image.select("SCL")
        clear = scl.remap(
            list(EarthEngineClient.SENTINEL_SCL_MASK_CLASSES),
            [0] * len(EarthEngineClient.SENTINEL_SCL_MASK_CLASSES),
            1,
        ).eq(1)
        red = image.select("B4").multiply(0.0001)
        green = image.select("B3").multiply(0.0001)
        nir = image.select("B8").multiply(0.0001)
        swir1 = image.select("B11").multiply(0.0001)
        ndvi_denominator = nir.add(red)
        ndbi_denominator = swir1.add(nir)
        ndvi = (
            nir.subtract(red)
            .divide(ndvi_denominator)
            .updateMask(ndvi_denominator.neq(0))
            .rename("ndvi")
        )
        ndbi = (
            swir1.subtract(nir)
            .divide(ndbi_denominator)
            .updateMask(ndbi_denominator.neq(0))
            .rename("ndbi")
        )
        ndwi_denominator = green.add(nir)
        ndwi = (
            green.subtract(nir)
            .divide(ndwi_denominator)
            .updateMask(ndwi_denominator.neq(0))
            .rename("ndwi")
        )
        return (
            ndvi.addBands(ndbi)
            .addBands(ndwi)
            .updateMask(clear)
            .copyProperties(image, ["system:time_start"])
        )

    def _require_initialized(self) -> None:
        if not self._initialized:
            raise EarthEngineInitializationError(
                "Earth Engine is not initialized. Run "
                "`python -m app.cli authenticate-earth-engine` first."
            )
