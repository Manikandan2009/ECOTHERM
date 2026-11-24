# ECOTHERM MVP Scope

## Goal

Produce a credible, reproducible local demonstration of heat and environmental patterns across Tamil Nadu and selected city study areas using real, dated, provenance-tracked data.

## MVP priorities

1. A clear dashboard and interactive map for the statewide 1 km grid and city 100 m grids.
2. A real April–June Landsat LST composite with quality masks, valid-observation counts, and visible missing coverage.
3. Sentinel-2 NDVI/NDBI layers with cloud/quality filtering and correct source-resolution notes.
4. Open-Meteo historical weather context with its temporal and spatial limits clearly explained.
5. Cached GeoJSON boundaries, CSV grid data, source/processing manifests, and an offline run path for successfully acquired exports.
6. Regional summaries and historical comparison only where the corresponding observations exist.
7. Evidence-linked cooling-intervention candidates, with no unsupported impact estimates.
8. A prediction interface that reports unavailable until validated data and models satisfy the documented criteria.

## Explicitly out of scope for this demo

- Any hardware, IoT, ESP32, sensors, or sensor-based collection.
- A hosted service is optional; local use must work without Docker, and deployment instructions are included.
- Database storage uses PostgreSQL/PostGIS when configured, with SQLite as the local fallback.
- ML forecasts, risk scores, or performance claims until target definition, sufficient real historical coverage, baselines, and spatial/temporal evaluation are complete.
- Automated cooling-impact claims, high-resolution thermal sharpening, or neighborhood-scale weather downscaling.
- Unverified city boundaries, fabricated fallback observations, and demo values presented as real.

## One-day demo path

Optimize the first runnable demo for a single reproducible acquisition window and cached outputs:

1. Confirm Earth Engine account/project access and source/boundary licensing.
2. Acquire and export Tamil Nadu and the three city study areas in manageable tasks/tiles.
3. Process QA masks, grids, indices, and provenance; inspect valid-data coverage before producing summaries.
4. Serve the resulting files locally through FastAPI and display them in the existing React application.
5. Keep unavailable metrics/layers visibly unavailable instead of blocking the app or inventing values.

If a provider is unavailable or Earth Engine access is not configured, explain the blocker. Only previously acquired, real and provenance-preserving caches can provide an offline data demo.

## MVP acceptance gate

- The application starts locally without Docker using SQLite when PostgreSQL/PostGIS is unavailable.
- A selected region and layer clearly show source, period, units, grid spacing, native spatial support, data coverage, and status.
- Map and summary values can be traced to cached source and processing manifests.
- Cloud, missing-data, and provider failures are visible and do not produce success-shaped fabricated data.
- The same inputs and processing version can be rerun reproducibly.
- No prediction or intervention impact is presented as measured unless it has actually been evaluated.
