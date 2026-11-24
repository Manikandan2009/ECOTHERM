# ECOTHERM

ECOTHERM is a software-only urban heat intelligence project for Tamil Nadu. The planned statewide analysis grid is 1 km; Chennai, Coimbatore, and Madurai have approximately 100 m detailed grids. The main LST season is April–June. Values are real, source-attributed observations or derived products; missing coverage is never replaced with fabricated data.

## Current milestone

See [PROGRESS.md](./PROGRESS.md). Milestones 2 and 3 establish the local Python/React setup and Earth Engine/Open-Meteo clients. Raster/grid processing, ML, and the complete dashboard are separate later milestones.

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

## Earth Engine authentication

Earth Engine credentials are not stored in `.env` or the repository. From `backend/` with the venv active:

```powershell
python -m app.cli authenticate-earth-engine
python -m app.cli check-earth-engine
```

The first command launches Google's supported authentication flow. The configured project ID is `ecotherm-515613`; that project must be enabled for Earth Engine and the signed-in user must have permission to use it. If access is missing, the CLI reports the initialization error rather than returning data-shaped fallbacks.

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
