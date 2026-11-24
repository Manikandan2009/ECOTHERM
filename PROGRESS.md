# ECOTHERM Progress

## Current status

- **Milestone 0 — Welcome landing page:** Complete and previously verified with a production build and browser route check.
- **Milestone 1 — Requirements, architecture, MVP scope, and folder structure:** Complete.
- **Milestone 2 — Project setup and dependencies:** Complete and verified.
- **Milestone 3 — Earth Engine and Open-Meteo clients:** Complete and verified.
- **Milestone 4 — Geospatial pipeline:** In progress; statewide and city real-data caches exist, and statewide WorldPop aggregation was corrected and verified.
- **Milestones 5–9:** Pending.

## Approved project scope

- Software-only urban heat intelligence platform for all of Tamil Nadu.
- Tamil Nadu statewide view: approximately 1 km grid.
- Detailed views: Chennai, Coimbatore, and Madurai at approximately 100 m grid spacing.
- Aggregate observations and population to Tamil Nadu districts; include population counts on the state and city grids when a licensed WorldPop raster is available.
- Use municipal ward boundaries for the three cities only when a source and license can be verified; otherwise rank explicitly labeled city grid cells. Aggregate all other Tamil Nadu areas by district.
- Main summer composite: April 1–June 30; default to the latest complete season (2026 at the time this plan was written), with the year configurable.
- Use real, provenance-tracked Landsat 8/9, Sentinel-2 (including NDWI), Open-Meteo, WorldPop, and OpenStreetMap data. Population is an estimated/modelled product, never live or census-accurate; record its year and use age structure only if a verified source is available. No fabricated observations or results.
- Collect OSM buildings, roads, hospitals, parks, and water points when obtainable; derive cell-level distances and density only from downloaded, attributed features. Attempt IMD/local station validation; if no appropriate air-temperature observations can be obtained, document validation as not done.
- A Random Forest downscaling product must be labeled "ESTIMATED (downscaled)" and report only measured spatial-CV errors. Landsat LST is surface temperature, not air temperature; higher-resolution predictions are estimates, not measurements.
- Heat risk is a configurable Exposure (0–100) × Vulnerability (0–100) index with documented component weights. Impact simulation and budget optimization must use editable unit-cost and cooling-range assumptions, disclose uncertainty, and never call assumed benefits validated impacts.
- Cache actual acquisition/processing outputs to files for the demo. Demo fixtures, if ever needed for tests, must be explicitly identified and kept separate from observations.
- Persist structured analysis in PostgreSQL + PostGIS when available; support SQLite as the local fallback.
- Provide Docker Compose and deployment documentation. Docker/PostgreSQL are not installed in the current environment, so their runtime verification may require a separate machine.
- District priorities and budget allocations use only measured/modelled inputs with explicit weights, editable cost assumptions, missing-data notes, and no unsupported cooling-effect estimates.
- Implement and verify Milestones 4–9 in order without pausing for approval between them.
- Milestone 10 (scheduled live updates) is explicitly deferred until the user approves it.

## Milestone 1 deliverables

- `docs/requirements.md`: confirmed requirements, constraints, scientific caveats, and acceptance criteria.
- `docs/architecture.md`: system components, data flow, initial API contract, storage and validation approach.
- `docs/mvp-scope.md`: first-demo priorities, explicit exclusions, and completion gates.
- Planned application, data, processing, test, and documentation folders scaffolded without prematurely implementing Milestones 2–9. The database directory from the original scaffold is an unused placeholder and remains out of scope.

## Milestones 2–3 completed

- Python backend package and virtual environment created. Core, geospatial, ML, and development dependencies installed from `backend/pyproject.toml`.
- Frontend map/chart dependencies installed and locked in `frontend/package-lock.json`.
- Added `.env.example`, root `.gitignore`, FastAPI app/health route, local run instructions, and initial file-backed configuration. Database, Docker, and deployment are now in scope per the latest approval.
- Earth Engine client uses project `ecotherm-515613`, local interactive authentication, Landsat 8/9 Collection 2 L2SP summer collections, QA masking, LST scaling to Celsius, and Sentinel-2 SCL masking with NDVI/NDBI products.
- Open-Meteo client requests ERA5-Land daily temperature and hourly temperature/humidity; it validates dates and arrays, records missing dates/null counts and provenance, and caches raw JSON plus normalized daily/hourly CSVs under ignored `data/cache/`.
- Live Earth Engine access was verified. For the single Chennai reference point (13.0827, 80.2707), the April–June 2026 collection query returned 12 intersecting Landsat scenes and 23 intersecting Sentinel-2 scenes before per-pixel validity assessment. Mapped band names were `lst_c`, and `ndvi`/`ndbi`.
- A real Open-Meteo reference-point request returned 91 daily and 2,184 hourly rows with no missing dates/null values for current variables. The provider resolved the coordinate to its ERA5-Land grid point. This is not a citywide or state-wide weather statistic.
- The initial precipitation request returned all-null values at the reference point and was excluded from the current weather response rather than interpreted as zero.
- Verification: 14 backend tests passed; backend dependency check and Python compile check passed; frontend production build passed; live `/health` and cached weather API smoke checks passed.

## Latest verified data and checks (2026-11-24)

- Tamil Nadu cache: 130,385 1 km cells, 130,380 valid LST cells (99.996%); 38 district summaries. Boundary-based city areas remain circular 15 km study extents, not municipal polygons; no verified ward polygons are available.
- April–June 2026 Landsat-derived LST composite: mean 41.68 °C and maximum 57.72 °C. These are **land-surface temperatures**, not air temperatures.
- WorldPop estimated/modelled 2025 population after corrected 1 km area-weighted aggregation: 80,214,043 over cells with valid estimates (92.08% coverage). The separate 2020 age/sex data are not 2025/2026 observations. District totals are slightly lower because grid centers, rather than fractional cell areas, are assigned to district polygons.
- Chennai's cached 100 m grid summary reports estimated/modelled 2025 population of 2,844,603 at 51.25% population-cell coverage. This is the circular 15 km study extent, not the municipality; missing population cells remain missing, not zero.
- Chennai WorldPop coverage is 51.25% because the retained 15 km circular study extent includes ocean/coastal and non-modelled areas: 36,172 of 70,573 clipped 100 m cells have valid WorldPop estimates, while 34,401 cells are nodata. This is not caused by raster clipping or `-9999` masking. A real municipal boundary would replace the circular extent in a future improvement.
- Madurai pipeline completed: 70,586 100 m circular-extent grid cells; 70,505 valid LST cells (99.885% coverage); mean LST 43.119 °C; maximum LST 55.796 °C. WorldPop 2025 modelled population totals 1,093,582 across 45,102 valid population cells (63.897% coverage). These are a 15 km circular study extent and not municipal-boundary observations.
- All-Tamil Nadu boundary expansion — Step 1 complete: 38 district ADM2 polygons from geoBoundaries 2021 are cached in `data/cache/processed/boundaries/districts.geojson`. Source: Pathways Data Pvt. Ltd., lgdirectory.gov.in. Licence: Open Data Commons Open Database License 1.0. The `/api/v1/districts` endpoint returns the list and GeoJSON; the dashboard region selector includes all 38 districts and the overview map displays their polygons.
- Step 1 boundary work did not acquire or rerun any statewide LST, population, satellite, or 1 km grid data. The existing statewide and city caches are unchanged.
- Stage 1 — District map interaction complete: polygon clicks select districts, Leaflet fit-bounds zooms to districts, selected polygons are highlighted and others dimmed, and Tamil Nadu restores the statewide view.
- Stage 2 — Real district boundaries complete: Chennai, Coimbatore, and Madurai now use cached geoBoundaries 2021 ADM2 district polygons rather than circular study extents. Source/licence metadata is retained; these remain district boundaries, not municipal ward boundaries.
- Stage 3 — Static district data complete: 38 district caches created from the cached 1 km 2026 statewide grid in 10 resumable batches of 4 (last batch 2 districts). Re-running batch 1 verified cache skips. Each district has CSV, GeoJSON and manifest with the April–June 2026 Landsat composite dates and WorldPop 2025 modelled population provenance.
- Region selector cleanup: only "Tamil Nadu" plus 38 district entries are shown. Chennai, Coimbatore, and Madurai circular-city entries were removed; those names now resolve through their single ADM2 district entry. District static manifests supply valid cached LST/population; existing city weather caches are reused for these three district-reference locations. Circular 100 m caches are no longer exposed as municipal boundaries.
- Stage 4 — Live district weather: `/api/v1/weather/live?district_id=...` uses Open-Meteo current forecast data, 15-minute file cache, 3 retries, and stale fallback from the last good cache. The frontend polls every 5 minutes and shows live/stale/unavailable plus Updated HH:MM. Satellite and population remain clearly labelled cached/modelled.
- Stage 5 — District risk layer: implemented only as a documented rule-based derived layer, not a validated prediction model. Exposure is within-district LST percentile; vulnerability combines low vegetation 40%, NDBI 35%, and WorldPop population-density 25%. Risk ≥75 is high-risk. People exposed is modelled population in high-risk cells. UHI is district mean LST minus the cached statewide mean LST. Missing evidence remains unavailable. Method: `docs/risk-method.md`.
- Stage 3 — Static district data: starting. The existing Tamil Nadu 1 km April–June 2026 LST/Sentinel/WorldPop cache will be clipped in batches of 4, without new Earth Engine acquisition.
- Stage 1 — District map interactions: in progress; Leaflet fit/select highlighting and polygon click selection are being finalized and tested.
- Open-Meteo ERA5-Land context for the statewide reference point: April–June daily mean temperature 30.67 °C and daily maximum 39.5 °C. This is coarse reanalysis, not a station measurement; wind was unavailable in the cached period.
- Earth Engine's corrected WorldPop grid calculation was sampled at Chennai, Coimbatore, and Madurai reference points. Corrected 1 km values were approximately 11,443, 9,305, and 12,008 people respectively; the earlier area-weighted-only output was approximately 95, 78, and 101. These are modelled estimates, not validation observations.
- Legacy statewide raster cells are corrected during local grid processing when the population aggregation tag is missing. Manifests record the correction and method version.
- The running dashboard API now returns the corrected population estimate. High-risk cells, people exposed to high heat, and urban-heat-island intensity remain unavailable (null); no risk model has been validated or implemented yet.
- Data gaps: OSM features were not acquired; municipal ward boundaries were not verified (grid-cell fallback remains explicit); IMD/local station air-temperature validation has not been completed.
- Latest verification: **17 backend tests passed**, Python `compileall` passed, Earth Engine access check passed (990 API algorithms), frontend production build passed, and `/api/v1/summary` returned the corrected cached values.
- Weather cache fix: the dashboard now reads persisted `weather_daily` rows and falls back to cached daily CSV files if SQLite is absent or has no matching city weather. The fetch CLI now persists successful cache hits and new responses into SQLite. Chennai, Coimbatore, and Madurai each expose ERA5-Land mean/max air-temperature context with the label date range April 1–June 30, 2026. Verification: **18 backend tests passed** and the frontend production build passed.

## Remaining Milestone 4 data gaps

- Attempt OSM acquisition again with clear timeout/partial-data reporting; until successful, do not calculate building density, amenity distances, or footfall proxies.
- Verify whether licensable ward boundaries are available for the three city study areas; otherwise preserve the documented grid-cell fallback.
- Attempt IMD/local station validation if an accessible, license-compatible source is identified. If none is available, mark air-temperature validation as not done in `docs/validation.md`.
- Ensure per-region weather and population provenance/coverage are exposed consistently; current state weather is a coarse reference-location series, not a spatially distributed grid layer.

## Remaining milestones

| Milestone | Scope | Status |
| --- | --- | --- |
| 2 | Project initialization, dependencies, configuration, and environment variables | Complete |
| 3 | Earth Engine Landsat/Sentinel-2 and Open-Meteo clients, authentication, provenance, and error handling | Complete |
| 4 | Sourced state/district/city/ward boundaries, satellite/weather/WorldPop/OSM acquisition, NDWI, grids and district aggregation, weather validation attempt, and database outputs | In progress |
| 5 | Leakage-safe baselines and Random Forest downscaling, measured spatial CV, uncertainty/feature importance, Heat Risk Index, and evidence-based ranking inputs | Pending |
| 6 | PostgreSQL/PostGIS with SQLite fallback, migrations, typed API for regions/layers/weather/population/predictions/analytics/recommendations/reports/priority/budget | Pending |
| 7 | Responsive dashboard, observed/derived/estimated/predicted map layers, ward/district priorities, people-exposed cards, live adjustable risk weights, and API integration | Pending |
| 8 | Evidence-linked intervention recommendations, assumption-labeled impact/budget optimizer, people-benefited ranking, per-ward PDF and CSV reports, and labeled cached demo mode | Pending |
| 9 | Pytest/Vitest, documentation and cost guide, `docs/validation.md`, Docker Compose, deployment instructions, and presentation script | Pending |

## Next step

Finish Milestone 4 by attempting OSM and station data acquisition, recording their availability clearly, and verifying cached city and district population coverage. Then continue Milestones 5–9 in order. Milestone 10 remains deferred until explicit approval.

## Constituency expansion update (2026-11-24)

- Added the supplied DataMeet `India_AC` shapefile under `data/cache/processed/boundaries/` as the constituency boundary source. The source manifest records `https://github.com/datameet/maps`, CC BY 4.0, and the 2008 delimitation year (post-2008 Tamil Nadu assembly boundaries).
- Validated the Tamil Nadu filter: exactly 234 records, 234 unique AC numbers, and no missing constituency names. There are 231 unique name strings because three names are each shared by two seats: Tiruchirappalli, Tiruppattur, and Vandavasi (SC). Seat number is included in each stable constituency ID to disambiguate these cases.
- Matched each constituency polygon to the cached 2021 district polygon with the largest intersection area in EPSG:6933. All 234 have a district match. Nine have less than 80% of polygon area within the assigned district; this is retained as a visible provenance/data-quality caveat because the constituency and district boundary vintages differ.
- Added `/api/v1/constituencies?district_id=...`, constituency summary lookup, and a live Open-Meteo weather endpoint path by constituency centroid. The dashboard now has a district-dependent constituency selector, polygon overlay/click selection, district dimming, max-zoom-capped fitBounds, and reset-to-district behavior.
- **Batch 1 of 8 complete:** 30/234 caches created under `data/cache/processed/constituencies/static_batches/`; summaries include LST, WorldPop, coverage, and the documented derived risk calculation.
- **Batch 2 of 8 complete:** 60/234 caches now created (30 in this batch), with existing caches skipped safely on reruns. Verification after batch 2: **23 backend tests passed** and frontend production build passed.
- **Batch 3 of 8 complete:** 90/234 caches now created (30 in this batch). Verification after batch 3: **23 backend tests passed** and frontend production build passed.
- **Batch 4 of 8 complete:** 120/234 caches now created (30 in this batch). Verification after batch 4: **23 backend tests passed** and frontend production build passed.
- **Batch 5 of 8 complete:** 150/234 caches now created (30 in this batch). Verification after batch 5: **23 backend tests passed** and frontend production build passed.
- **Batch 6 of 8 complete:** 180/234 caches now created (30 in this batch). Verification after batch 6: **23 backend tests passed** and frontend production build passed.
- **Batch 7 of 8 complete:** 210/234 caches now created (30 in this batch). Verification after batch 7: **23 backend tests passed** and frontend production build passed.
- **Batch 8 of 8 complete:** all 234 constituency cache entries created (24 in the final batch). Verification after batch 8: **23 backend tests passed** and frontend production build passed.
- Name audit found no missing names. AC 45 is malformed in the supplied source as `Kilvaithinankuppam(SC` (unclosed parenthesis); the source string is preserved and flagged in both boundary manifests rather than silently corrected. Three repeated labels are disambiguated by AC number.
- Data caveat: district “rasters” were not present in the workspace. Constituency summaries use cached statewide 1 km grid-cell centers, not a resampled 100 m raster. No Earth Engine rerun or fabricated values were used. Constituencies with no matching cached cell remain unavailable.
- Original constituency cache batches 1–8 are complete; the following correction batches regenerated those same cache entries after the non-finite exposure bug was fixed.
- Cache correction audit found `people_exposed_high_heat` serialized as non-finite (`NaN`) in all 234 existing manifests because no grid cells met the current high-risk threshold. Fixed the aggregation to return a measured zero for an empty high-risk set and made the dashboard repository treat any non-finite persisted number as unavailable rather than emitting invalid API data. Added a regression test.
- Cache correction batch 1/8: regenerated 30 constituency summaries from the existing statewide grid; no Earth Engine acquisition. Verification: **25 backend tests passed** and frontend production build passed (existing >500 kB chunk warning).
- Cache correction batch 2/8: regenerated 30 more summaries (60/234 corrected). Verification: **25 backend tests passed** and frontend production build passed (existing >500 kB chunk warning).
- Cache correction batch 3/8: regenerated 30 more summaries (90/234 corrected). Verification: **25 backend tests passed** and frontend production build passed (existing >500 kB chunk warning).
- Cache correction batch 4/8: regenerated 30 more summaries (120/234 corrected). Verification: **25 backend tests passed** and frontend production build passed (existing >500 kB chunk warning).
- Cache correction batch 5/8: regenerated 30 more summaries (150/234 corrected). Verification: **25 backend tests passed** and frontend production build passed (existing >500 kB chunk warning).
- Cache correction batch 6/8: regenerated 30 more summaries (180/234 corrected). Verification: **25 backend tests passed** and frontend production build passed (existing >500 kB chunk warning).
- Cache correction batch 7/8: regenerated 30 more summaries (210/234 corrected). Verification: **25 backend tests passed** and frontend production build passed (existing >500 kB chunk warning).
- Cache correction batch 8/8: regenerated the final 24 summaries; all 234 entries are refreshed. Verification: **25 backend tests passed** and frontend production build passed (existing >500 kB chunk warning).

## Map inspection verification

- Added click-to-inspect behavior backed by `/api/inspect` and `/api/v1/inspect`; cached raster values are used directly, with unavailable reasons for missing 100 m coverage, masked cells, or outside-study-area clicks. No interpolation or statewide 1 km fallback is presented as a 100 m cell value.
- The Leaflet map now reuses a single inspection popup instead of accumulating popups. A browser check switching from a Chennai inspection to a Coimbatore inspection showed one popup; the outside-Tamil-Nadu click displayed "Outside study area" in that same popup.
- Browser verification also confirmed the popup includes coordinates, district/constituency, LST composite and observation count, difference from constituency mean when available, WorldPop estimate, and regional Open-Meteo status/time. Missing Coimbatore 100 m grid coverage was reported unavailable with its reason.
- Final verification after the popup lifecycle fix: **28 backend tests passed**; `npm.cmd run build` passed TypeScript and the Vite production build. Vite reports the existing >500 kB bundle-size warning.
- Milestone 10/live scheduling remains deferred; no live update scheduler was started.

## Compact inspection popup update (2026-11-24)

- Redesigned the map inspection popup with a constituency-first bold header, district line, four compact metric rows, muted "Unavailable" values with reason tooltips, and collapsed Landsat observation/date details.
- Capped the popup at 260 px (measured browser width: 258 px). Browser checks covered a Chennai cell with cached values, a Coimbatore point outside the cached 100 m city grid (reported as "Unavailable"), and a point outside Tamil Nadu. The popup remained single-instance; missing-value reasons stayed in the info tooltips.
- Expanded Details in the browser and confirmed it contains valid Landsat observations, composite dates, source, and observation-count note.
- Verification: frontend TypeScript and production build passed. Existing Vite >500 kB chunk-size warning remains.

## Satellite basemap and LST overlay (2026-11-24)

- Goal 1 was cancelled at the user's request. Restored click inspection to the prior city-grid-only behavior and regenerated the 38 district cache manifests/GeoJSON files in their pre-fallback v1 shape; no statewide fallback values are used by point inspection.
- Added a Map/Satellite switch. Satellite imagery uses Esri World Imagery with attribution; an optional Esri roads/places labels overlay has its source attribution. No Google tiles or API keys are used.
- District and constituency boundaries remain visible and use brighter outlines on satellite imagery. The basemap, labels, overlay toggle, and opacity are held in dashboard state and remain selected while changing region/constituency.
- Added `/api/v1/map/lst/{z}/{x}/{y}.png` for the cached statewide 1 km Landsat raster. Tiles use nearest-neighbor reprojection, transparent nodata, and a 25–55+ °C legend with an opacity control; the overlay does not smooth or interpolate LST values.
- Browser verification: switched between Map and Satellite with labels and LST enabled, received HTTP 200 for raster tiles, adjusted opacity to 0.8, and changed to Chennai/Thousand Lights without losing layer choices. Click-to-inspect returned constituency/district and cached cell values on both basemaps. Screenshot showed satellite imagery, bright boundary outlines, the heat-cell colors, and controls/legend.
- Verification: **32 backend tests passed**; `npm.cmd run build` passed TypeScript and the production build. The existing Vite >500 kB chunk warning remains.

## Click inspection statewide fallback (2026-11-24)

- Added the cached statewide 1 km CSV grid as a point-inspection fallback only when no 100 m city-grid cell covers the click. Existing 100 m cells remain preferred; masked/nodata cells are not replaced with another resolution.
- The popup now tags LST and population with the selected cell resolution. Constituency mean difference is computed from the clicked cell only when both values are available.
- Browser verification at Kalasapakkam, Tiruvannamalai returned observed/derived LST 40.1 °C (1 km), +1.1 °C versus its cached constituency mean, and modelled population 865 (1 km cell). The actual cached cell returned 44.8968 °C and population 12,782 in the direct API probe; the browser point was a different map cell.
- This restores only statewide point inspection; district/constituency summary aggregation and other cancelled Goal 1 work remain unchanged.
- Verification: **32 backend tests passed** and `npm.cmd run build` passed. The existing Vite >500 kB chunk warning remains.

## Missing dashboard metrics (2026-11-24)

- Constituency UHI now derives from the cached constituency mean LST minus the cached statewide 1 km mean; non-finite or unavailable inputs remain unavailable. For Neyveli this is 40.8948 °C − 41.6827 °C = **−0.8 °C** (rounded for display).
- Open-Meteo readiness now reflects the selected district/constituency live or stale weather response instead of reporting "Missing" when the air-temperature card already has a value.
- OpenStreetMap features remain marked "Not acquired"; no OSM-derived values are fabricated.
- Verification: **33 backend tests passed**, frontend production build passed, and browser check for Neyveli showed UHI −0.8 °C plus "Live · Updated 14:06" for Open-Meteo. The existing Vite >500 kB chunk warning remains.

## Tamil Nadu OpenStreetMap and dashboard recovery (2026-11-24)

- Added `process-osm-extract` to process the cached Geofabrik Southern Zone PBF locally, filter features against Tamil Nadu's cached boundary, and persist a provenance-bearing JSON summary. The extract is 560,395,545 bytes; its SHA-256 is recorded in the summary.
- Final statewide mapped-feature counts: **2,074,215 unique objects**—1,036,462 buildings, 999,350 roads, 8,797 health sites, 1,659 parks, 22,983 water features, 4,914 bus stops, and 211 markets. Explicit `building=no` and `building=ruins` tags are excluded. Category counts can overlap; OSM coverage is incomplete and non-uniform. GDAL reported some invalid/open polygon rings, so affected geometries may be omitted.
- The summary API and dashboard now expose the OSM counts. The dashboard also derives the existing rule-based heat-risk metrics from 120,051 complete cached grid cells. No cell reached the ≥75 threshold (maximum score 70.49), so the current derived high-risk-cell and exposed-population values are both 0; this is not a claim that no heat hazard exists. The statewide reference difference is 0 °C by definition and is labeled as a baseline, not an urban heat-island estimate.
- Restarted the FastAPI backend and verified `/api/v1/summary?region_id=tamil_nadu&season_year=2026` plus the browser dashboard at `http://127.0.0.1:5173/dashboard`. The page loads 41.7 °C mean LST, 80,214,043 estimated population, 30.7 °C ERA5-Land mean air temperature, the derived risk values, and all OSM counts.
- Verification: **35 backend tests passed**; frontend TypeScript and production build passed. Vite retains its existing >500 kB bundle-size warning. OpenStreetMap attribution, license, method, and limits are documented in `docs/data-sources.md`.

## Heat Map Explorer (2026-11-24)

- Implemented the Heat Map Explorer as a full-width map view using the cached Tamil Nadu Landsat LST raster and district/constituency boundaries. Entering the page enables the LST layer; map/satellite basemaps, labels, opacity, legend, region selection, and click-to-inspect remain available.
- The view identifies the April–June 2026 cloud-masked composite and 1 km cell resolution. It does not interpolate the cached LST raster.
- Browser verification confirmed the Heat Map Explorer heading, enabled LST layer and legend, expanded map (447 px in the tested viewport), working basemap toggle, and hidden overview-only source panel. The LST tile endpoint returned HTTP 200 (`image/png`, 46,786 bytes).
- Verification: `npm.cmd run build` passed; the existing Vite >500 kB bundle-size warning remains.

## Satellite Analysis (2026-11-24)

- Added a Satellite Analysis page using the existing cached April–June 2026 1 km raster and stored regional grid observations. LST, NDVI, NDBI, and NDWI are independently selectable with legends, opacity, map/satellite basemaps, labels, and district/constituency boundaries.
- Added nearest-neighbour map tile rendering for Sentinel-2 NDVI, NDBI, and NDWI, plus a regional summary endpoint reporting cached means and coverage without substituting values for missing data.
- The page explains Landsat/Sentinel source roles, composite dates, resolution, and that optical index values are dimensionless. No new Earth Engine acquisition was performed.
- Tamil Nadu cache summary: 130,385 1 km cells; mean LST 41.68 °C (99.996% valid), NDVI 0.403, NDBI 0.015, and NDWI −0.452 (each optical index 100% valid in the cached grid).
- Verification: **38 backend tests passed**, frontend production build passed, summary API returned the cached statistics, and all four tile endpoints returned HTTP 200 PNGs. Browser checks confirmed each layer's selected state/legend and a working Satellite basemap. Existing Vite >500 kB chunk warning remains.

## AI Predictions readiness (2026-11-24)

- Added the AI Predictions dashboard page and `/api/v1/predictions/status`. The page presents available cached evidence separately from any forecast, explains target/baseline/spatial/temporal qualification gates, and displays an explicit unavailable state.
- The SQLite training store contains one distinct summer season (2026): 130,385 statewide cells with 130,380 valid LST values. The `ml/` directory has no trained model or validation artifact. No target/lead time or held-out spatial/temporal evaluation is established, so no model was trained and no predictions are shown.
- Browser verification confirmed the unavailable state, 2026-only season inventory, qualification checklist, observed LST context and no forecast map. The prediction status API returned HTTP 200 with the recorded season/sample counts.
- Verification: **41 backend tests passed** and `npm.cmd run build` passed. The existing Vite >500 kB chunk-size warning remains.

## Staged dashboard build — Stage 1: Heat Map Explorer (2026-11-24)

- Heat Map Explorer now always opens on the OpenStreetMap street basemap with the LST overlay enabled, legend visible, and opacity adjustable. Region and constituency fit-bounds controls and map click inspection remain active.
- Browser verification: street basemap and LST overlay were selected; clicking the map returned a popup with district, constituency, LST, WorldPop population, and regional live air temperature plus observation dates/source.
- Verification: **41 backend tests passed**, `npm.cmd run build` passed, district API returned all 38 districts. The existing Vite >500 kB chunk warning remains.

## Staged dashboard build — Stage 2: Satellite Analysis (2026-11-24)

- Added the cached per-constituency NDVI/LST scatter endpoint and chart. The chart filters to valid paired cells only and shows its Pearson correlation, cell count, resolution, composite dates, and separate source descriptions.
- Satellite Analysis opens on Esri World Imagery with district/constituency boundaries above it. NDVI, built-up index (NDBI), NDWI, and LST overlays have independent controls, legends, and opacity. The satellite/LST swipe uses the same cached map layers and a position slider.
- Browser verification on Chennai's Anna Nagar constituency loaded 13 cached paired 1 km cells for April 1–June 30, 2026 (Pearson r = −0.781); the swipe slider, Esri imagery pane, and boundary overlay rendered. The displayed correlation is an association, not a causal effect.
- Regional cached summary cards show an explicit no-data reason when a constituency has no aggregate SQLite summary; the per-cell chart remains independently available from the constituency cache.
- Verification: **43 backend tests passed**, `npm.cmd run build` passed, and `/health` returned `ok`. The existing Vite >500 kB chunk warning remains.

## Staged dashboard build — Stage 3: Environmental Analytics (2026-11-24)

- Added a cached analytics endpoint and a sortable table spanning 38 districts and 234 constituencies with mean LST, modelled 2025 population, LST cell coverage, and mean NDVI labelled as a vegetation-greenness proxy (not percent green cover). Every populated metric includes its source, 1 km aggregation grid, and applicable date/year.
- Added two-district side-by-side comparisons, including cached air temperature only as reference-location context. ERA5-Land spatial resolution is explicitly reported as unrecorded in the cache rather than assumed.
- Added a date-labelled view of each district's cached April–June 2026 seasonal composite. No month-specific composites exist; each month is marked "Unavailable" with the reason, and the seasonal value is not assigned to individual months.
- Browser verification: all 272 region rows loaded; sort order changed in both directions; district comparison updated from Chennai/Coimbatore to Chennai/Madurai; cached composite and month-gap labels rendered.
- Verification: **45 backend tests passed**, `npm.cmd run build` passed, and the analytics API returned 38 districts and 234 constituencies. The existing Vite >500 kB chunk warning remains.

## Staged dashboard build — Stage 4: AI Prediction (2026-11-24)

- Added a standardized linear-regression LST estimate model using cached 1 km district grids with NDVI and NDBI. A deterministic district-group split holds out 25% of districts; no test-district cells are used for fitting. NDBI is explicitly labelled as a built-up-index proxy, not built-up share.
- The cached 2026 run held out 10 districts (38,113 cells) from 28 training districts (91,700 cells): R² **0.468**, MAE **2.86 °C**, and 90th-percentile absolute error **5.67 °C**. Relative standardized-coefficient importance: NDVI **72.5%**, NDBI **27.5%**.
- Added the regional input list and NDVI what-if slider (+0 to +20 percentage points on the NDVI index, with NDBI fixed). For the statewide mean inputs, +0.20 NDVI yielded an LST change estimate of **−4.4 °C**, with a broad empirical change range of **−15.8 to +6.9 °C** (±2× held-out p90 error). The UI labels this "estimate, not a forecast" and states the range is not a confidence interval or causal effect.
- Future-season forecast remains unavailable: only the 2026 summer season is cached. Method and limitations are documented in `docs/risk-method.md`.
- Verification: **46 backend tests passed**, `npm.cmd run build` passed, the estimate API returned disjoint train/test districts and measured metrics, and browser checks confirmed the +0/+20 slider outputs. The existing Vite >500 kB chunk warning remains.

## Staged dashboard build — Stage 5: Priorities and Budget (2026-11-24)

- Added a cached constituency-priority API using a transparent 0–100 derived score: heat exposure percentile × population relative to the maximum cached constituency population × bounded low-greenness proxy ((1 − mean NDVI) / 2). The page states that NDVI is a proxy, not a percent green-cover measurement; no intervention cost or unit price is supplied.
- The API returned valid inputs and scores for all **234 constituencies**. Each input and derived score exposes its data source, grid resolution, and composite/model date; missing inputs retain their cached reason and make that row's score unavailable.
- Added four selectable intervention types and blank, user-entered per-constituency cost fields. A user-entered total budget is split across the selected number of top positive scores in proportion to score; costs do not affect the allocation. CSV export includes scores, source/provenance, manual intervention/cost entries, allocations, and missing-data reasons.
- Browser verification loaded 234 rows; with a user-entered budget of 100,000, 20 rows received proportional allocations totaling 100,000 (floating-point display precision); all 234 cost fields were initially blank.
- Verification: **48 backend tests passed**, `npm.cmd run build` passed, and `/api/v1/priorities/constituencies?season_year=2026` returned `available` with 234 scored constituencies. The existing Vite >500 kB chunk-size warning remains.

## Staged dashboard build — Stage 6: Reports and Methods (2026-11-24)

- Added a district/constituency/state report preview with a browser Print / Save as PDF action. The report map snapshot is drawn from cached boundary GeoJSON only; remote basemap imagery and live weather are excluded.
- The report shows cached LST, valid-cell coverage, WorldPop population/coverage, NDVI greenness proxy, and regional air-temperature context, each with its source, applicable date/year and spatial support. Missing inputs retain explicit "Unavailable" reasons. Limits include modelled population, regional weather resolution, seasonal-only coverage, sensor support and absent cache-update timestamps.
- Added an eight-source methods register covering DataMeet constituency boundaries (2008 delimitation, CC BY 4.0), district boundaries (2021, ODbL 1.0), Landsat Collection 2 Level 2, Sentinel-2 SR Harmonized, WorldPop R2025A/v1 (CC BY 4.0), Open-Meteo ERA5-Land (CC BY 4.0), Esri World Imagery attribution, and OpenStreetMap/Geofabrik (ODbL 1.0). Where a license/version is not stored, the page says so rather than inferring it.
- Browser verification for Anna Nagar rendered the cached boundary snapshot and print action; LST **43.5 °C**, population **165,927**, NDVI **0.236**, 1 km aggregation grid, and the April 1–June 30, 2026 composite were shown with provenance. Constituency air temperature uses the parent district reference context and is not described as a constituency measurement. All eight methods rows rendered.
- Verification: **48 backend tests passed** and `npm.cmd run build` passed. The existing Vite >500 kB chunk-size warning remains.

## Staged dashboard build — Stage 7: Settings and About (2026-11-24)

- Added browser-local settings for Heat Map Explorer basemap, Celsius/Fahrenheit display, default region, and preferred 1 km/100 m resolution. Preferences are validated, persisted across reloads, and storage/invalid-region errors are shown. The 100 m option is explicitly a preference only; the cached district/constituency dataset remains 1 km.
- Temperature conversion is applied to displayed LST, weather, UHI differences, analytics, satellite charts/legend, prediction errors and estimates, map-inspection popups, and reports. Source values remain in Celsius.
- Added dataset freshness information for satellite composites, WorldPop, boundaries, Open-Meteo historical/live weather, OSM and Esri. Missing cache-update timestamps are explicitly reported as unavailable; the live-weather refresh button is the only manual refresh and is disabled until a district/constituency is selected.
- Added an About attribution/licence section for DataMeet, district boundaries, USGS Landsat, Copernicus/ESA Sentinel-2, WorldPop, Open-Meteo, Esri and OpenStreetMap/Geofabrik.
- Browser verification confirmed the Fahrenheit overview value (Chennai LST **108.8 °F**), saved Fahrenheit/default-Chennai settings after reload, an enabled live-weather refresh for the selected district and a returned update status. Test settings were restored to Celsius, Tamil Nadu, street basemap and 1 km.
- Final verification: **48 backend tests passed**; `npm.cmd run build` passed TypeScript and the production build. The existing Vite >500 kB chunk-size warning remains.

## Final dashboard integrity audit (2026-11-24)

- Null and non-finite numeric values now display "Unavailable" instead of a dash or invalid number; missing inspection-popup values show their reason inline. Cache freshness uses a clear reason when timestamps or composite dates are not present.
- District and constituency coverage percentages are derived only from cached valid-cell and total-cell counts when the cache omits the percentage. Invalid counts remain unavailable. Regression coverage confirms both summary paths.
- Valid zero-risk results display numeric **0**, and a zero-change what-if result reads "No change." Source, grid resolution, and applicable period are shown with overview values.
- Browser verification: all eight sections loaded; no uncaught page errors, browser console errors/warnings, or failed local HTTP responses. The Heat Map Explorer opened on streets with LST overlay and legend enabled. Tamil Nadu / Celsius / street / 1 km preferences persisted after reload.
- Backend `/health` returned `ok`; the Tamil Nadu dashboard showed 100% LST grid coverage, 92% population coverage, and cached April 1–June 30, 2026 dates. District coverage was derived from 1,160 valid of 1,160 cached cells.
- Final verification: **49 backend tests passed**, `npm.cmd run build` and workspace diagnostics reported no errors. The pre-existing Vite bundle-size warning (>500 kB) remains. Remote map-tile requests may abort during page navigation; no local API requests failed.

## Data completion follow-up (2026-11-24)

- Acquired the missing Open-Meteo ERA5-Land daily temperature series for the 35 district reference points that were not cached. All 38 districts now have complete April 1–June 30, 2026 coverage (91 daily rows per district); the 234 constituency analytics rows display their parent-district context with an explicit limitation, not a local measurement.
- The analytics API returns all 272 district/constituency rows with LST, population, NDVI, coverage, and air-temperature context populated; no core metric or weather-context rows are missing. Weather context is a 0.1° (~11 km) reanalysis estimate at a reference point, not area-averaged or observed station data.
- Fixed constituency satellite summaries to aggregate the already cached constituency grid CSV when the SQLite aggregate is absent. All 234 constituency caches now return LST, NDVI, NDBI, and NDWI computed from valid cells with per-layer coverage, 1 km resolution, and April 1–June 30, 2026 dates.
- Current UI wording uses numeric zero for true zero risk/exposure results and "Unavailable" plus a reason for inputs not present in the cache. Monthly LST composites beyond the seasonal April–June composite and cache-update timestamps remain unrecorded; neither is inferred.
- Browser verification showed the complete Tamil Nadu overview (including the numeric zero results and source metadata) and all four satellite metrics for Pappireddippatti. No page or console errors were observed; tile/API requests aborted during region navigation.
- Verification after these changes: **50 backend tests passed**, the TypeScript/Vite production build passed, and workspace diagnostics reported no errors. The existing Vite chunk-size warning (>500 kB) remains.

