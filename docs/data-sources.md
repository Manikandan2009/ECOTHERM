# Data Sources and Acquisition

This document records the source choices and access requirements for Milestone 3. Dataset terms, collection metadata, and API limits can change; verify them again when acquiring a new season and retain the collection IDs and retrieval metadata with each output.

## Google Earth Engine

- **Cloud project:** `ecotherm-515613` (configured as `ECOTHERM_EARTH_ENGINE_PROJECT_ID`).
- **Authentication:** local user authentication through the Earth Engine Python client. Run `python -m app.cli authenticate-earth-engine`, then `python -m app.cli check-earth-engine`. The Cloud project must have Earth Engine enabled and the signed-in user must have permission. Credentials are stored by Google's authentication tooling, never in the repository or frontend.
- **Account/access:** Earth Engine access and quota depend on the account/project registration and usage terms. The application reports project/API failures rather than substituting data.
- **Landsat 8:** `LANDSAT/LC08/C02/T1_L2`.
- **Landsat 9:** `LANDSAT/LC09/C02/T1_L2`.
- **Landsat LST band:** `ST_B10`, Kelvin = stored value × `0.00341802` + `149`; Celsius is Kelvin − `273.15`. Select surface-temperature products (`PROCESSING_LEVEL=L2SP`); `L2SR` scenes do not have valid ST_B10.
- **Landsat QA:** `QA_PIXEL` fill, dilated cloud, cirrus, cloud, cloud shadow, and snow bits are masked; `QA_RADSAT` is checked for saturation/terrain-occlusion flags. USGS documents known cloud/cloud-shadow-related ST errors and persistent missing ST areas related to ASTER GED inputs; cloud masking does not eliminate all retrieval uncertainty.
- **Thermal support:** the catalog reports 30 m pixel spacing for distributed bands, while the Landsat thermal sensor support is about 100 m. Do not describe the 30 m resampling or a 100 m grid as finer native thermal detail.
- **Sentinel-2:** `COPERNICUS/S2_SR_HARMONIZED` Level-2A surface reflectance. Reflectance bands are stored scaled by 10,000. `SCL` classes no-data, saturated/defective, cloud shadow, low/unclassified cloud, medium/high cloud, cirrus, and snow/ice are excluded. NDVI uses B8/B4; NDBI uses B11/B8. B8/B4 are 10 m and B11 is 20 m.
- **Sentinel limitations:** Sentinel-2 has no thermal band in this product. It supports optical indices and imagery, not LST.
- **Licensing:** Landsat products are provided by USGS; Sentinel-2 is Copernicus/ESA. Preserve provider attribution, collection/product IDs, and applicable source terms in exported manifests.
- **Satellite Analysis map:** the cached April–June 2026 raster exposes Landsat LST plus Sentinel-2 NDVI, NDBI, and NDWI as separate layers on the 1 km analysis grid. Each layer uses nearest-neighbour tile reprojection, transparent nodata, and per-layer cached-cell coverage statistics for the selected region. NDVI/NDBI/NDWI are dimensionless optical indices (not percentages); do not interpret them as surface temperature or land-cover classifications.

Official references:

- [Earth Engine authentication](https://developers.google.com/earth-engine/guides/auth)
- [Landsat 8 Collection 2 Level 2](https://developers.google.com/earth-engine/datasets/catalog/LANDSAT_LC08_C02_T1_L2)
- [Landsat 9 Collection 2 Level 2](https://developers.google.com/earth-engine/datasets/catalog/LANDSAT_LC09_C02_T1_L2)
- [Sentinel-2 SR Harmonized](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED)

## WorldPop population

- **2025 total population:** `WorldPop/GP/100m/R2025A/v1/pop`, filtered to India and year 2025. Values are modelled population counts on a 3 arc-second grid (approximately 100 m at the equator), not live counts or census observations. This product includes estimates for multiple years; the cached ECOTHERM season uses 2025.
- **Age/sex structure:** `WorldPop/GP/100m/pop_age_sex_cons_unadj`, year 2020. Children and elderly counts are derived from the supplied age bands. This is a separate, older modelled product; its age shares must not be presented as 2025 or 2026 observations.
- **1 km aggregation:** source pixel counts are scaled by the target/source pixel-area ratio before area-weighted summation. A cached legacy raster created before this correction is detected by its missing processing tag and corrected during grid processing. The method/version and whether the legacy correction was applied are stored in the grid manifest.
- **100 m city grid:** source values are reprojected to the analysis grid; this does not increase WorldPop's native detail. City regions are circular study extents around sourced OSM reference points, not municipal boundaries.
- **License and limits:** WorldPop products are distributed under CC BY 4.0; retain attribution and distinguish the 2025 total-population estimate from the 2020 age structure. Verify the current product catalog and year coverage before refreshing.

Official references:

- [WorldPop 2025 population collection](https://developers.google.com/earth-engine/datasets/catalog/WorldPop_GP_100m_R2025A_v1_pop)
- [WorldPop age/sex collection](https://developers.google.com/earth-engine/datasets/catalog/WorldPop_GP_100m_pop_age_sex_cons_unadj)
- [WorldPop data portal](https://www.worldpop.org/)

## Open-Meteo Historical Weather API

- **Endpoint:** `https://archive-api.open-meteo.com/v1/archive`.
- **Authentication:** no API key is required for eligible non-commercial free use.
- **Requested model:** ERA5-Land (`models=era5_land`) for consistent historical context. The API response records model identity and returned coordinates/elevation.
- **Variables:** daily maximum, minimum, and mean 2 m temperature (°C), plus hourly 2 m temperature (°C) and relative humidity (%); timezone is `Asia/Kolkata`.
- **Resolution and status:** ERA5-Land is approximately 0.1° (about 11 km). It is reanalysis/model data, not a local thermometer reading and not a 100 m observation. The response explicitly identifies values as reanalysis estimates.
- **Availability/limits:** historical availability and update delay are provider-dependent. Free service terms publish request limits (currently fewer than 10,000 calls/day, 5,000/hour, and 600/minute) and restrict free use to non-commercial purposes. The provider does not guarantee uninterrupted availability or accuracy.
- **License/attribution:** Open-Meteo data are under CC BY 4.0 according to its terms; preserve attribution. Confirm current terms before public or commercial use.
- **Caching:** successful responses are saved as provenance-bearing JSON under `data/cache/raw/open_meteo/`, with normalized daily and hourly CSV files under `data/cache/processed/open_meteo/`. CSV rows retain requested and provider-resolved coordinates, model, and reanalysis status; the JSON retains full units and missing-data provenance. An API error or corrupt cache is surfaced; no empty or invented weather series is returned.
- **Coverage:** daily missing dates and hourly returned counts are recorded, as are per-variable null counts. In the initial real Chennai reference-point check, the requested ERA5-Land `precipitation_sum` values were null for the full April–June 2026 window, so precipitation is not part of the current client response. Nulls are never treated as zero.

Official references:

- [Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)
- [Open-Meteo terms](https://open-meteo.com/en/terms)
- [Open-Meteo license](https://open-meteo.com/en/licence)

## OpenStreetMap features

- **Extract:** [Geofabrik Southern Zone latest PBF](https://download.geofabrik.de/asia/india/southern-zone.html), processed locally from `data/cache/raw/openstreetmap/southern-zone-latest.osm.pbf`.
- **Coverage:** tagged mapped buildings, roads, hospitals/clinics, parks, water features, bus stops, and markets whose geometries intersect the cached Tamil Nadu boundary. Geofabrik's extract includes areas outside Tamil Nadu; processing filters those features against the state boundary.
- **Counts:** output is a distinct OSM-object count by feature category, not an estimate of all real-world facilities or infrastructure. OpenStreetMap coverage varies by place and category; an absent mapped object does not establish that the real-world feature is absent.
- **Processing limits:** category counts can overlap, while the total is deduplicated by OSM object ID. The GDAL OSM reader reported some unclosed or invalid polygon rings; affected objects may be omitted. A 5 km buffered spatial read is intersected with the cached state boundary.
- **License and attribution:** Open Database License 1.0 (ODbL); credit © OpenStreetMap contributors. Preserve attribution and review ODbL obligations before redistributing derived databases.
- **Cached output:** `data/cache/processed/openstreetmap/tamil_nadu_summary.json` records category counts, the source URL, extract SHA-256, state-boundary fingerprint, processing time, GDAL version, and method.
- **Command:** from the repository root, run `backend\.venv\Scripts\python.exe -m app.cli process-osm-extract`; add `--force-refresh` to recompute a matching cache.

Official references:

- [Geofabrik Southern Zone extract](https://download.geofabrik.de/asia/india/southern-zone.html)
- [OpenStreetMap copyright and ODbL](https://www.openstreetmap.org/copyright)

## Acquisition period

The configured main composite window is April 1 through July 1 exclusive, so all of April, May, and June are included. The initial year is 2026 and can be changed explicitly. Earth Engine scene collections and Open-Meteo requests use the same configured season year. Requested dates, actual valid dates, and missing dates must remain distinguishable.

## Live client verification (2026-11-23)

- Earth Engine authentication and API access succeeded with Cloud project `ecotherm-515613`.
- At the explicit Chennai reference point (requested coordinates 13.0827, 80.2707), the April–June 2026 collection query returned 12 intersecting Landsat 8/9 `L2SP` scenes and 23 intersecting Sentinel-2 scenes. The mapped products expose `lst_c` and `ndvi`/`ndbi`, respectively. These are source-scene counts at one point before per-pixel valid-observation assessment; they are not Tamil Nadu-wide coverage counts or city heat statistics.
- An Open-Meteo request for the same named reference point returned 91 daily and 2,184 hourly rows, with no missing dates or null values for the currently requested variables. The model grid resolved to 13.099998, 80.20001, which demonstrates the coarse-grid support; this is not a citywide average.
- The raw weather response is cached locally under `data/cache/raw/open_meteo/` and excluded from source control. The historical precipitation variable was all-null in the initial check and is therefore excluded from the current client response.

## Latest cached real-data pipeline (2026-11-24)

- Tamil Nadu has 130,385 1 km cell records and 38 district summaries. The April–June 2026 Landsat/Sentinel composites and Open-Meteo ERA5-Land weather context are cached locally. These are derived summer composites and reanalysis, not air-temperature station measurements.
- WorldPop 2025 population is estimated at approximately 80.21 million across cells with 92.08% valid population coverage. A corrected sum aggregation was verified against Earth Engine outputs at Chennai, Coimbatore, and Madurai reference points. District totals differ slightly from the state grid total because cell centers are assigned to districts and boundary-edge areas are not fractionally allocated.
- Age/sex values are the 2020 WorldPop estimate and have lower spatial coverage; they are not aligned in year with the 2025 total-population estimate.
- OSM buildings/roads/amenities were not successfully acquired, municipal ward boundaries were not verified, and IMD/local station validation has not been completed. Do not infer these data from the cached satellite products.
