from pathlib import Path

import pandas as pd


class GridExportError(RuntimeError):
    """Raised when a cached grid export cannot be read or validated."""


def read_grid_export(
    cache_dir: Path,
    *,
    region_id: str,
    season_year: int,
    resolution_m: int,
    columns: tuple[str, ...],
) -> pd.DataFrame | None:
    path = (
        cache_dir
        / "processed"
        / "grids"
        / f"{region_id}_{resolution_m}m_{season_year}.csv"
    )
    if not path.is_file():
        return None
    try:
        available_columns = set(pd.read_csv(path, nrows=0).columns)
        missing_columns = set(columns) - available_columns
        if missing_columns:
            raise GridExportError(
                f"Cached grid export {path.name} is missing columns: "
                f"{', '.join(sorted(missing_columns))}."
            )
        metadata_columns = tuple(
            column
            for column in ("region_id", "season_year", "resolution_m")
            if column in available_columns
        )
        frame = pd.read_csv(
            path,
            usecols=tuple(dict.fromkeys((*metadata_columns, *columns))),
        )
    except GridExportError:
        raise
    except (OSError, ValueError, pd.errors.EmptyDataError, pd.errors.ParserError) as exc:
        raise GridExportError(
            f"Could not read cached grid export {path.name}: {exc}"
        ) from exc
    metadata_matches = (
        ("region_id" not in frame or set(frame["region_id"].astype(str)) == {region_id})
        and (
            "season_year" not in frame
            or set(pd.to_numeric(frame["season_year"], errors="coerce"))
            == {season_year}
        )
        and (
            "resolution_m" not in frame
            or set(pd.to_numeric(frame["resolution_m"], errors="coerce"))
            == {resolution_m}
        )
    )
    if not frame.empty and not metadata_matches:
        raise GridExportError(
            f"Cached grid export {path.name} contains mismatched region, season, "
            "or resolution metadata."
        )
    return frame
