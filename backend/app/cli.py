import argparse
import asyncio
import json
import sys
from datetime import date
from typing import Sequence

from app.core.settings import get_settings
from app.services.earth_engine import EarthEngineClient, EarthEngineError
from app.services.open_meteo import OpenMeteoClient, OpenMeteoError
from app.services.summer_pipeline import run_summer_pipeline
from app.services.study_areas import BoundaryDataError
from app.services.earth_engine import EarthEngineDataError
from app.services.grid_processing import GridProcessingError
from app.services.open_street_map import (
    OpenStreetMapError,
    process_geofabrik_extract,
)
from app.repositories.sqlite_store import GridPersistenceError
from app.repositories.sqlite_store import save_weather_observations
from app.services.district_aggregates import cache_district_static_batches
from app.services.constituency_aggregates import (
    cache_constituency_static_batches,
    prepare_constituency_boundaries,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ecotherm")
    commands = parser.add_subparsers(dest="command", required=True)

    authenticate = commands.add_parser(
        "authenticate-earth-engine",
        help="Run Google's local Earth Engine authentication flow.",
    )
    authenticate.add_argument(
        "--force",
        action="store_true",
        help="Request fresh Earth Engine credentials.",
    )

    commands.add_parser(
        "check-earth-engine",
        help="Verify Earth Engine credentials and project API access.",
    )

    weather = commands.add_parser(
        "fetch-weather",
        help="Fetch and cache daily Open-Meteo archive data for one point.",
    )
    weather.add_argument("--location-id", required=True)
    weather.add_argument("--latitude", type=float, required=True)
    weather.add_argument("--longitude", type=float, required=True)
    weather.add_argument("--start-date", type=date.fromisoformat, required=True)
    weather.add_argument("--end-date", type=date.fromisoformat, required=True)
    weather.add_argument(
        "--force-refresh",
        action="store_true",
        help="Reacquire data even if a matching cache file already exists.",
    )
    acquire = commands.add_parser(
        "acquire-summer-data",
        help="Acquire and process real summer satellite, weather, and population data.",
    )
    acquire.add_argument("--year", type=int, default=2026)
    acquire.add_argument(
        "--region-id",
        action="append",
        choices=("tamil_nadu", "chennai", "coimbatore", "madurai"),
        help="Limit processing to a region; repeat to select multiple regions.",
    )
    acquire.add_argument("--force-refresh", action="store_true")
    acquire.add_argument("--skip-weather", action="store_true")
    acquire.add_argument("--skip-osm", action="store_true")
    process_osm = commands.add_parser(
        "process-osm-extract",
        help="Process the cached Geofabrik Southern Zone extract for Tamil Nadu.",
    )
    process_osm.add_argument(
        "--force-refresh",
        action="store_true",
        help="Reprocess the extract even when a matching summary is cached.",
    )
    district_cache = commands.add_parser(
        "cache-district-static",
        help="Cache static district LST and WorldPop values in resumable batches.",
    )
    district_cache.add_argument("--year", type=int, default=2026)
    district_cache.add_argument("--batch-size", type=int, default=4)
    district_cache.add_argument("--start-batch", type=int, default=1)
    district_cache.add_argument("--force-refresh", action="store_true")
    commands.add_parser(
        "prepare-constituencies",
        help="Validate the DataMeet shapefile and map Tamil Nadu constituencies to districts.",
    )
    constituency_cache = commands.add_parser(
        "cache-constituency-static",
        help="Cache constituency summaries from the existing statewide grid in batches of 30.",
    )
    constituency_cache.add_argument("--year", type=int, default=2026)
    constituency_cache.add_argument("--batch", type=int, required=True)
    constituency_cache.add_argument("--force-refresh", action="store_true")
    return parser


def _earth_engine_client() -> EarthEngineClient:
    return EarthEngineClient(get_settings().earth_engine_project_id)


async def _fetch_weather(args: argparse.Namespace) -> int:
    settings = get_settings()
    client = OpenMeteoClient(
        archive_url=settings.open_meteo_archive_url,
        cache_dir=settings.cache_dir,
        timeout_seconds=settings.open_meteo_timeout_seconds,
    )
    result = await client.fetch_daily(
        location_id=args.location_id,
        latitude=args.latitude,
        longitude=args.longitude,
        start_date=args.start_date,
        end_date=args.end_date,
        force_refresh=args.force_refresh,
    )
    database_path = settings.cache_dir / "processed" / "ecotherm.sqlite"
    daily_count, hourly_count = save_weather_observations(
        database_path,
        result.data,
    )
    print(
        f"{'Cache hit' if result.from_cache else 'Fetched and cached'}: "
        f"{daily_count} daily rows persisted, "
        f"{hourly_count} hourly rows persisted"
    )
    print(f"Raw response: {result.path}")
    print(f"Daily CSV: {result.daily_csv_path}")
    print(f"Hourly CSV: {result.hourly_csv_path}")
    print(
        f"Provider: Open-Meteo Historical Weather API; "
        f"model: {result.data.provenance.model}; "
        f"requested point: {result.data.provenance.requested_latitude}, "
        f"{result.data.provenance.requested_longitude}"
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "authenticate-earth-engine":
            client = _earth_engine_client()
            client.authenticate(force=args.force)
            print(
                "Earth Engine authentication completed for project "
                f"{client.project_id}."
            )
            return 0
        if args.command == "check-earth-engine":
            client = _earth_engine_client()
            algorithm_count = client.check_access()
            print(
                f"Earth Engine access verified for project {client.project_id}; "
                f"{algorithm_count} API algorithms available."
            )
            return 0
        if args.command == "fetch-weather":
            return asyncio.run(_fetch_weather(args))
        if args.command == "acquire-summer-data":
            result = run_summer_pipeline(
                get_settings(),
                year=args.year,
                region_ids=args.region_id,
                force_refresh=args.force_refresh,
                skip_weather=args.skip_weather,
                skip_osm=args.skip_osm,
            )
            print(json.dumps(result, indent=2, default=str))
            return 2 if result["errors"] else 0
        if args.command == "process-osm-extract":
            result = process_geofabrik_extract(
                get_settings().cache_dir,
                force_refresh=args.force_refresh,
            )
            print(json.dumps(result, indent=2, default=str))
            return 0
        if args.command == "cache-district-static":
            result = cache_district_static_batches(
                cache_dir=get_settings().cache_dir,
                season_year=args.year,
                batch_size=args.batch_size,
                start_batch=args.start_batch,
                force_refresh=args.force_refresh,
            )
            print(json.dumps(result, indent=2, default=str))
            return 0
        if args.command == "prepare-constituencies":
            result = prepare_constituency_boundaries(get_settings().cache_dir)
            print(json.dumps(result, indent=2, default=str))
            return 0
        if args.command == "cache-constituency-static":
            result = cache_constituency_static_batches(
                cache_dir=get_settings().cache_dir,
                season_year=args.year,
                batch_size=30,
                start_batch=args.batch,
                force_refresh=args.force_refresh,
            )
            print(json.dumps(result, indent=2, default=str))
            return 0
    except EarthEngineError as exc:
        print(f"Earth Engine error: {exc}", file=sys.stderr)
        return 2
    except OpenMeteoError as exc:
        print(f"Open-Meteo error: {exc}", file=sys.stderr)
        return 2
    except (
        BoundaryDataError,
        EarthEngineDataError,
        GridProcessingError,
        GridPersistenceError,
        OpenStreetMapError,
    ) as exc:
        print(f"Data pipeline error: {exc}", file=sys.stderr)
        return 2
    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
