# ECOTHERM Architecture

## Scope and implementation order

This architecture describes the approved Tamil Nadu project. Milestone 1 defined the initial structure and interfaces; the latest approval expands implementation to PostgreSQL/PostGIS with a SQLite fallback, Docker Compose, and deployment documentation. The local demo must remain runnable without Docker and must use real, cached data.

## System context

```text
 Google Earth Engine                         Open-Meteo Archive
 Landsat 8/9 L2 + Sentinel-2 L2A              Historical weather
            \                                      /
             \                                    /
              +-- authenticated acquisition scripts --+
                                                        |
       sourced Tamil Nadu/city boundaries --------------+
                                                        v
             cloud/quality masks + provenance manifests
                                                        |
                 aligned grid & feature processing
                   (GeoPandas / Rasterio / NumPy)
                    /                         \
           cached GeoJSON/CSV             validated ML pipeline
           and source assets              (scikit-learn)
                    \                         /
                     FastAPI data/services API
                               |
                 React + Leaflet + Recharts UI
```

Earth Engine is used server-side for catalog access and batch exports; credentials must be configured locally and must never be embedded in the frontend or committed. Open-Meteo is a separate provider with its own terms and availability. Every export carries provider/product identity and retrieval/processing metadata.

## Repository structure

```text
.
├── PROGRESS.md
├── docs/
│   ├── architecture.md
│   ├── mvp-scope.md
│   └── requirements.md
├── frontend/                         # Existing Vite/React application
│   └── src/
│       ├── api/
│       ├── assets/
│       ├── components/               # Existing
│       ├── features/
│       ├── hooks/
│       ├── pages/                    # Existing
│       ├── types/
│       └── tests/
├── backend/
│   ├── app/
│   │   ├── api/v1/
│   │   ├── core/
│   │   ├── repositories/
│   │   ├── schemas/
│   │   └── services/
│   └── tests/
│       ├── integration/
│       └── unit/
├── data/
│   ├── cache/
│   │   ├── exports/
│   │   ├── processed/
│   │   └── raw/
│   └── demo/                         # Isolated, provenance-labeled demo assets
├── data_acquisition/
├── database/
│   └── migrations/
├── geospatial/
├── ml/
├── scripts/
├── shared/
│   └── schemas/
└── tests/
    ├── data_quality/
    ├── fixtures/
    ├── integration/
    └── unit/
```

## Component responsibilities

- **`data_acquisition/`**: Earth Engine and Open-Meteo clients, boundary sourcing, authentication checks, retries with explicit failure reporting, export task tracking, and source manifests.
- **`geospatial/`**: boundary validation, grid generation, QA masks, per-source aggregation, temporal matching, derived indices, missing-data handling, and CSV/GeoJSON export.
- **`ml/`**: target construction, leakage-safe feature datasets, baseline/model training, blocked validation, metric and uncertainty output, and prediction serialization.
- **`backend/app/`**: FastAPI endpoints, request/response schemas, application settings, and service/repository boundaries. It serves only available, provenance-backed data.
- **`database/`**: schema, migrations, spatial indexes, and database setup. PostgreSQL uses PostGIS; SQLite is the local fallback and does not provide equivalent spatial SQL.
- **`frontend/`**: React pages and feature modules, typed API client, Leaflet map/layers, Recharts analytics, and accessible loading/error/no-data states.
- **`shared/schemas/`**: versioned API contract artifacts or generated client types. Keep generated frontend types synchronized from the backend OpenAPI contract rather than hand-maintaining duplicate schemas.
- **`data/cache/`**: local, reproducible exports and processing outputs. Keep credentials and temporary Earth Engine task files out of this directory. Large/generated artifacts must not be confused with source code.
- **`data/demo/`**: only explicitly documented assets for an offline demo. Any real observation retains its source manifest; synthetic test fixtures belong in `tests/fixtures/`, never among observations.

## Geospatial and data flow

1. Select the season and a validated boundary version. The default season is April 1–June 30, 2026; other years are explicit configuration.
2. Query Landsat 8/9 Collection 2 Level 2 surface temperature and Sentinel-2 Level-2A reflectance in Earth Engine. Apply product-specific QA masks before seasonal compositing.
3. Acquire dated Open-Meteo archive variables for the selected study context. Keep the provider's spatial resolution and model nature explicit.
4. Generate deterministic metric grid IDs: 1 km for Tamil Nadu and 100 m for city study areas. Persist CRS, grid origin, resolution, boundary version, and processing version.
5. Aggregate each input to its analysis grid using documented statistics. Keep per-cell valid counts, source date ranges, masks, and nodata status.
6. Write versioned manifests and cached results. GeoJSON stores sourced boundary geometry; CSV stores cell IDs, centroid coordinates, grid size, measurements, units, quality counts, dates, source IDs, and processing version.
7. Persist processed grid records through a repository backed by PostgreSQL/PostGIS when configured or SQLite otherwise. Retain file exports for auditability and offline review.

Landsat LST has approximately 100 m native thermal support: the 100 m city grid does not create finer thermal detail. Sentinel-2 vegetation and built-up layers have different source-band resolutions. Open-Meteo is regional/coarse weather context, not a 100 m weather observation. Do not mask these distinctions behind a common grid.

## Initial API contract

All responses include a stable schema version and provenance/quality metadata. Exact Pydantic models are implemented with the backend milestone.

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Service and loaded-cache health; no fabricated data status |
| `GET /api/v1/regions` | Available, sourced region IDs, boundaries, and supported resolutions |
| `GET /api/v1/summary?region_id=...&season_year=...` | Coverage counts and statistics computed from valid cached observations |
| `GET /api/v1/grid?region_id=...&resolution_m=...&layer=...&season_year=...` | Grid values, units, valid counts, nodata/quality flags, and provenance |
| `GET /api/v1/map/lst/{z}/{x}/{y}.png` | Cached 1 km Landsat LST map tiles; nearest-neighbor sampling preserves source cells and nodata stays transparent |
| `GET /api/v1/weather?region_id=...&start=...&end=...` | Available archive weather series and provider metadata |
| `GET /api/v1/predictions/status?region_id=...` | Cached-season and model qualification status; unavailable forecasts stay explicit |
| `GET /api/v1/predictions?...` | Validated model output only; explicit unavailable response if no qualified model exists |
| `GET /api/v1/recommendations?...` | Evidence-backed candidate interventions with inputs and limitations |
| `GET /api/v1/reports?...` | Later milestone: downloadable summary generated from available data |

Routes must distinguish “no cached data”, “partially covered”, “provider unavailable”, and “processing failed”; never substitute an apparently successful empty dataset.

## Storage and configuration

- Processed grid records use PostgreSQL/PostGIS when configured, or SQLite when no PostgreSQL URL is set. GeoJSON/CSV and manifests remain reproducible exports.
- Configuration is environment-driven. Actual Earth Engine credentials and database secrets stay local and ignored. Docker Compose provides PostGIS for environments with Docker installed.
- The exact boundary and API terms, licenses, attribution, catalog IDs, quota limits, and acquisition dates are recorded during the data-source milestone rather than guessed here.

## ML and explainability

The provisional target is a next-period seasonal LST anomaly or regional-reference risk class per cell. Fix target and forecast lead time before training. Features must predate the target; split by time and geographically blocked areas; compare with previous-season and historical-climatology baselines. Report only held-out metrics and sample counts. If there are insufficient valid seasons/cells, return prediction unavailable. Explanations and recommendations must identify the evidence used and must not imply causal impact.

## Milestone gates

Milestones 2–9 are governed by `PROGRESS.md`. Each milestone must have its own implementation and relevant verification completed before progress is marked complete; the latest approval directs implementation to proceed sequentially without pausing between milestones.
