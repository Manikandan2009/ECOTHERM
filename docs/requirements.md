# ECOTHERM Requirements

## Product objective

ECOTHERM is a software-only platform for exploring urban heat and environmental conditions using satellite observations, public weather data, geospatial processing, and—only when supported by adequate validation—machine-learning predictions.

The first implementation targets Tamil Nadu, India:

- Statewide: an approximately 1 km analysis grid.
- Detailed study areas: Chennai, Coimbatore, and Madurai at approximately 100 m grid spacing.
- District-level summaries and population aggregation on statewide, city, and district areas when the population source supports them.
- Ward-level summaries for Chennai, Coimbatore, and Madurai only when open/licensed ward geometries are available; otherwise use and label the city study grid rather than inventing ward boundaries.
- Main summer observation window: April 1 through June 30, selected by year. The initial default is the latest complete window, 2026; the year must remain configurable.

Study-area boundary sources, dates, licenses, and versions must be recorded before data are exported. Do not silently substitute a district, bounding box, or other area for an unavailable municipal boundary.

## Functional requirements

1. Provide an overview dashboard, heat-map explorer, satellite analysis, predictions, environmental analytics, reports, and settings.
2. Present Landsat-derived land-surface temperature (LST), Sentinel-2 NDVI/NDBI/NDWI, Open-Meteo weather context, and optional OSM features as distinct products.
3. Offer the Tamil Nadu grid, detailed city grids, and district summaries, including region selection, layer selection, location lookup, and clear legends.
4. Support acquisition and processing from scripts that can be rerun and resumed, with cached output for repeatable offline demonstrations.
5. Show source, acquisition period, processing status, units, quality/valid-observation counts, and whether a value is observed, derived, estimated, or predicted.
6. Expose data gaps, cloud/quality limitations, stale caches, and API/authentication failures explicitly.
7. Provide historical analytics, regional comparisons, and evidence-linked cooling-intervention candidates.
8. Add ML predictions only after the target, baseline, data sufficiency, and spatial/temporal evaluation have been established. If these conditions are unmet, report that predictions are unavailable.
9. Keep demo inputs and outputs reproducible and provenance-backed. Persist structured outputs in PostgreSQL/PostGIS when configured and support a SQLite fallback. Provide Docker Compose and deployment instructions; external credentials remain local.
10. Display WorldPop population as an estimated/modelled product with its source year, resolution, license, and limitations; never call it live or census-accurate. Include age shares only if present in a verified source product.
11. Compute district priorities and budget allocations only from available population and environmental evidence. Clearly label editable unit costs as assumptions, expose weights and data gaps, and do not estimate cooling benefits without cited and applicable evidence.
12. Compute building density and distances to mapped hospitals, parks, and water points from attributed OpenStreetMap features when coverage is available; absent OSM objects must remain missing, not become zero-distance or zero-count values.
13. Estimate downscaled LST only with a documented Random Forest trained on co-located coarse Landsat LST and Sentinel-2/OSM predictors, spatially held-out validation, and measured error. Label every output "ESTIMATED (downscaled)" and do not present it as measured LST.
14. If appropriate IMD or local station air-temperature observations cannot be obtained and aligned, state that air-temperature validation is not done. Satellite LST is surface temperature and must never be described as air temperature.

## Data and scientific requirements

### Landsat 8/9

- Use a documented Landsat Collection 2 Level 2 surface-temperature product and retain product IDs and processing metadata.
- Apply QA masks for fill, cloud, cirrus, cloud shadow, snow, and saturated/invalid pixels before compositing.
- Convert stored surface-temperature values using the product's documented scale and offset; report LST in degrees Celsius only after that conversion.
- Landsat thermal measurements have approximately 100 m native spatial support. A 100 m output grid does not create finer thermal information. Do not describe resampled pixels as higher-resolution observations.
- Use a per-cell seasonal statistic (initially median) with valid-scene counts and date ranges. Do not fill missing pixels with fabricated or unmarked values.

### Sentinel-2

- Use a documented Level-2A surface-reflectance collection and mask invalid, cloud, cirrus, shadow, and snow classes using the product's quality layer.
- Compute NDVI from red and near-infrared reflectance and NDBI from shortwave-infrared and near-infrared reflectance. Record the input bands, mask, scale, and aggregation method.
- Preserve the distinction between index source resolution and output grid spacing. In particular, NDBI uses a 20 m SWIR band; a 100 m grid is an aggregation, not a 100 m sensor measurement.
- Sentinel-2 is not a thermal source and must not be presented as providing LST.

### Open-Meteo

- Use the historical/archive endpoint for dated context and record requested coordinates, variables, timezone, units, retrieval time, and response metadata.
- Treat weather values as model-based, spatially coarse context. Do not imply that they are observed at every 100 m grid cell or downscaled neighborhood measurements.
- Honor the selected API terms, attribution, and rate limits at implementation time.

### Population

- Use a verified WorldPop 100 m population-count product when available for the selected year and geography; record product ID, year, units, resolution, license, and retrieval/processing date.
- Mark every value as modelled/estimated population, not current live population or a census count. Do not extrapolate a product year to another year without a documented model.
- Use age structure only when the exact selected product supplies it and document its age bands, year, and uncertainty. Otherwise omit age vulnerability inputs rather than fabricate them.
- Aggregate counts to grids and district polygons using area-weighted raster sums and preserve nodata; do not treat missing pixels as zero population.
- The current verified Earth Engine catalog identifies the R2025A v1 population product (2015–2030) and a separate age/sex product available for 2020 only. Record these distinct product years and do not imply that 2020 age structure is a 2025/2026 estimate.

### OpenStreetMap and accessibility

- Record the retrieval timestamp, query coverage, ODbL attribution, and object types for buildings, roads, hospitals, parks, and water points.
- Calculate network/Euclidean distance only as explicitly named and only when the corresponding feature coverage is complete enough to support it; document whether distance is straight-line or network-based.

### Grids, boundaries, and missing data

- Use a documented metric, equal-area working CRS for grids covering the whole state and persist its EPSG identifier and grid origin.
- Define stable grid IDs from region, CRS, resolution, and row/column coordinates so that exports can be joined reproducibly.
- Record the boundary source, version/date, license, attribution, and geometry validity. City extents must use sourced boundaries or be explicitly labeled study extents.
- Preserve nodata and quality flags. Summaries must report valid-cell counts and must not turn missing coverage into zero or a normal-looking value.
- Do not interpolate a coarse weather field onto the 100 m grid in a way that suggests additional spatial information.

## Prediction and recommendation requirements

- Candidate prediction target: a future summer per-cell LST anomaly or risk class relative to a documented regional reference distribution. Final target and lead time must be fixed before model fitting.
- Prevent temporal leakage: prediction features must be available before the target period. Prevent spatial leakage with geographically blocked evaluation in addition to temporal holdout.
- Compare against simple baselines (for example, previous-season value and historical per-cell/region climatology). Report metrics only when measured on held-out data, with sample counts and uncertainty.
- If usable seasons or valid coverage are inadequate, display “prediction unavailable” rather than a made-up score or a mislabeled heuristic.
- Recommendations may be rule-based candidates supported by mapped evidence such as high relative LST and low vegetation. Explain the inputs and limitations; do not claim a causal cooling benefit or forecast intervention impact without evaluation.
- District priority and budget outputs must expose the configurable weights, source-year mismatch, data coverage, population benefited, editable unit-cost assumptions, and per-district caps. Cooling potential remains "not estimated" unless validated research supports a specific, applicable estimate.
- Heat-risk scores are composite indices, not probabilities: define Exposure and Vulnerability scales and normalize their product, display the factors and weights, and recompute rankings when weights change.
- Budget impact ranges must be clearly labeled as scenario assumptions unless a directly applicable study supports them. Do not invent source citations; display low/medium/high ranges, assumptions, and uncertainty, and keep measured benefit distinct from modeled or assumed benefit.

## Non-functional requirements

- Local, reproducible setup for a hackathon demo; external credentials remain in ignored local environment files and never in source control.
- Structured logs and actionable errors for failed acquisition, exports, processing, and API requests.
- Accessible, responsive UI with units, legends, keyboard-operable controls, and visible provenance.
- Automated tests for masks/units/grid IDs/data quality, API behavior, and ML split/leakage rules. Tests must not present fixtures as real measurements.
- Respect source licenses, attribution, Earth Engine account/project requirements, and each provider's terms. Document exact dataset versions and limits during acquisition implementation.

## Acceptance criteria for a real-data demo

- A user can select Tamil Nadu or one of the three named city study areas and inspect available LST, NDVI/NDBI, and weather layers.
- The UI displays the data year/window, source, spatial support, valid coverage, units, and provenance for each layer.
- An unavailable source or missing season produces an explicit, useful empty/error state; it never falls back to invented observations.
- Re-running the pipeline against the same source window produces traceable, versioned cached exports.
- Any prediction shown has documented target, baseline, spatial and temporal holdouts, measured metrics, uncertainty, and limitations; otherwise prediction UI reports unavailability.
