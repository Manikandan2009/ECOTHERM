from typing import cast

import ee
import pytest

from app.services.earth_engine import (
    EarthEngineClient,
    EarthEngineDataError,
    EarthEngineInitializationError,
    summer_window,
)


def test_summer_window_is_april_through_june() -> None:
    window = summer_window(2026)
    assert window.start.isoformat() == "2026-04-01"
    assert window.end_exclusive.isoformat() == "2026-07-01"


def test_summer_window_rejects_year_before_landsat_8() -> None:
    with pytest.raises(ValueError, match="between 2013 and 9998"):
        summer_window(2012)


def test_initialize_uses_configured_project(monkeypatch: pytest.MonkeyPatch) -> None:
    initialized: list[str] = []
    monkeypatch.setattr(ee, "Initialize", lambda **kwargs: initialized.append(kwargs["project"]))

    EarthEngineClient("ecotherm-515613").initialize()

    assert initialized == ["ecotherm-515613"]


def test_initialize_reports_missing_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_initialize(**_: object) -> None:
        raise ee.EEException("credentials unavailable")

    monkeypatch.setattr(ee, "Initialize", fail_initialize)
    client = EarthEngineClient("ecotherm-515613")

    with pytest.raises(EarthEngineInitializationError, match="authenticate-earth-engine"):
        client.initialize()


def test_collection_requires_initialization() -> None:
    client = EarthEngineClient("ecotherm-515613")
    region = cast(ee.Geometry, object())

    with pytest.raises(EarthEngineInitializationError, match="not initialized"):
        client.landsat_summer_collection(region, 2026)


def test_landsat_collection_uses_both_missions_and_exclusive_july_end(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeCollection:
        def __init__(self, collection_id: str) -> None:
            self.collection_id = collection_id
            self.date_range: tuple[str, str] | None = None
            self.merged: FakeCollection | None = None

        def filterBounds(self, _: object) -> "FakeCollection":
            return self

        def filterDate(self, start: str, end: str) -> "FakeCollection":
            self.date_range = (start, end)
            return self

        def filter(self, _: object) -> "FakeCollection":
            return self

        def map(self, _: object) -> "FakeCollection":
            return self

        def merge(self, other: "FakeCollection") -> "FakeCollection":
            self.merged = other
            return self

    collections: list[FakeCollection] = []

    def make_collection(collection_id: str) -> FakeCollection:
        collection = FakeCollection(collection_id)
        collections.append(collection)
        return collection

    monkeypatch.setattr(ee, "ImageCollection", make_collection)
    monkeypatch.setattr(ee.Filter, "eq", lambda *_: object())
    monkeypatch.setattr(ee.Filter, "lt", lambda *_: object())
    client = EarthEngineClient("ecotherm-515613")
    client._initialized = True
    region = cast(ee.Geometry, object())

    combined = client.landsat_summer_collection(region, 2026)

    assert [item.collection_id for item in collections] == list(client.LANDSAT_COLLECTIONS)
    assert all(item.date_range == ("2026-04-01", "2026-07-01") for item in collections)
    assert combined is collections[0]
    assert collections[0].merged is collections[1]


def test_count_scenes_reports_server_errors() -> None:
    class FailedCollection:
        def size(self) -> "FailedCollection":
            return self

        def getInfo(self) -> int:
            raise ee.EEException("quota unavailable")

    client = EarthEngineClient("ecotherm-515613")
    client._initialized = True

    with pytest.raises(EarthEngineDataError, match="quota"):
        client.count_scenes(cast(ee.ImageCollection, FailedCollection()))
