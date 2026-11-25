# ECOTHERM

ECOTHERM is a software-only urban heat intelligence project for Tamil Nadu. The planned statewide analysis grid is 1 km; Chennai, Coimbatore, and Madurai have approximately 100 m detailed grids. The main LST season is April–June. Values are real, source-attributed observations or derived products; missing coverage is never replaced with fabricated data.

## Current milestone

See [PROGRESS.md](./PROGRESS.md). Milestone 3 provides the Earth Engine/Open-Meteo clients; Milestone 4 includes geospatial exports and the dashboard's cached-data path. ML and later product work remain tracked separately.

## Prerequisites

- Node.js and npm for the frontend.
- Python 3.12 or later for the backend.
- A Google Earth Engine-enabled account and access to Cloud project `ecotherm-515613` to run Earth Engine operations. Authentication is interactive and local.
- Internet access for uncached Open-Meteo requests.

No database, Docker, deployment platform, or hardware is required for the local demo.

## Setup

From the repository root in PowerShell:

```powershell
Copy-Item .env.example .env
cd backend
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[geospatial,ml,dev]"
```

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

If PowerShell blocks activation, use the venv interpreter directly:

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -e ".\backend[geospatial,ml,dev]"
```

## Run

Start the API from `backend/` with the virtual environment active:

```powershell
uvicorn app.main:app --reload
```

The API health check and interactive API documentation are at `http://127.0.0.1:8000/health` and `http://127.0.0.1:8000/docs`.

Run the frontend from `frontend/`:

```powershell
npm run dev
```

## Deploy

The repository includes a Render Blueprint for the frontend and API. See [the deployment guide](./docs/deployment.md) for publishing the app and provisioning its cached data.

## Earth Engine authentication

Earth Engine credentials are not stored in `.env` or the repository. From `backend/` with the venv active:

```powershell
python -m app.cli authenticate-earth-engine
python -m app.cli check-earth-engine
```

The first command launches Google's supported authentication flow. The configured project ID is `ecotherm-515613`; that project must be enabled for Earth Engine and the signed-in user must have permission to use it. If access is missing, the CLI reports the initialization error rather than returning data-shaped fallbacks.

To export the April 1–June 30, 2026 products for Tamil Nadu (1 km) and Chennai, Coimbatore, and Madurai (about 100 m), run these commands from `backend/` after activating the virtual environment:

```powershell
Set-Location backend
.\.venv\Scripts\Activate.ps1
python -m app.cli authenticate-earth-engine
python -m app.cli check-earth-engine
python -m app.cli acquire-summer-data --year 2026 --region-id tamil_nadu --region-id chennai --region-id coimbatore --region-id madurai --skip-weather --skip-osm
```

The export uses Landsat 8/9 Collection 2 Level 2 ST_B10 with QA_PIXEL cloud/shadow masking, Sentinel-2 SR Harmonized with SCL masking for NDVI/NDBI, and WorldPop 2025 population estimates. Cell CSVs and polygon GeoJSONs are written to `data/cache/processed/grids/`; source rasters and manifests are kept under `data/cache/raw/earth_engine/` and `data/cache/processed/manifests/`. The statewide 1 km WorldPop values are aggregated as population counts; 100 m products do not imply finer Landsat thermal detail. The command can take a while and requires Earth Engine access.

The dashboard API reads these grid CSVs for statewide/city summary and satellite metrics, falling back to SQLite when a grid CSV is absent. Its map tiles use the cached raster, and its administrative overlays use the cached boundary GeoJSON. Start the API and frontend in separate terminals:

```powershell
Set-Location backend
uvicorn app.main:app --reload
```

```powershell
Set-Location frontend
npm run dev
```

Fetch and cache daily/hourly weather for a named reference point (the coordinates are explicit inputs, not assumed city averages):

```powershell
python -m app.cli fetch-weather --location-id chennai_reference_point --latitude 13.0827 --longitude 80.2707 --start-date 2026-04-01 --end-date 2026-06-30
```

The cached response is tagged as ERA5-Land reanalysis at roughly 0.1° support. It is a point query against a coarse model grid, not a 100 m city observation.

## Open-Meteo

Open-Meteo Historical Weather API calls require no API key for eligible non-commercial use. Raw responses are cached under `data/cache/raw/open_meteo/`; daily and hourly CSV exports are written under `data/cache/processed/open_meteo/`. Attribution and license requirements apply. The free API has published request limits and is not guaranteed to be continuously available. Cached weather retains its requested location, dates, model, units, and retrieval time.

## Tests and build

From `backend/` with the venv active:

```powershell
python -m pytest
```

From `frontend/`:

```powershell
npm run build
```

Tests use explicitly marked fixtures/mocks and do not claim those fixtures are real observations. Earth Engine authentication and provider availability are prerequisites for live data, not for offline unit tests.

## Data integrity

- Earth Engine products are identified by collection, season, masking/processing version, and export metadata.
- Landsat thermal data have approximately 100 m native support; a finer output grid does not add thermal detail.
- Sentinel-2 supplies optical reflectance and derived indices, not LST.
- Open-Meteo archive values are model/reanalysis-based and spatially much coarser than the detailed grids.
- API/provider failures, incomplete coverage, and unavailable credentials are explicit states. No observations, metrics, or predictions are invented.
