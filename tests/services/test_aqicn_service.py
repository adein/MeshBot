"""
Tests for services/aqicn_service.py

All tests are fully isolated: no filesystem access (config.yaml) and no network
calls (requests.get) are made. Both dependencies are patched via monkeypatch /
unittest.mock.
"""

import copy
import pytest
import requests

from unittest.mock import MagicMock, mock_open, patch

from services.aqicn_service import AirQualityService
from models.air_quality import (
    AirQualityData,
    AirQualityCityData,
    AirQualityCurrentMeasurementData,
    AirQualityForecastData,
    AirQualityDailyForecastData,
    AirQualityForecastItemData,
    AirQualityTimeData,
)

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

MOCK_CONFIG = {
    "services": {
        "aqicn_service": {
            "api_key": "test-key-123"
        }
    }
}

# Mirrors the real AQICN API response structure (based on a live call)
FULL_API_RESPONSE = {
    "status": "ok",
    "data": {
        "aqi": 27,
        "idx": 5330,
        "attributions": [
            {"url": "https://www.epa.gov/", "name": "US EPA"},
            {"url": "https://waqi.info/", "name": "World Air Quality Index Project"},
        ],
        "city": {
            "geo": [42.737499, -84.536102],
            "name": "Lansing, Michigan, USA",
            "url": "https://aqicn.org/city/usa/michigan/lansing",
            "location": "",
        },
        "dominentpol": "o3",
        "iaqi": {
            "dew":  {"v": -1},
            "h":    {"v": 80},
            "no2":  {"v": 1.6},
            "o3":   {"v": 27.2},
            "p":    {"v": 1014.2},
            "pm10": {"v": 2},
            "pm25": {"v": 5},
            "so2":  {"v": 2},
            "t":    {"v": 2},
            "w":    {"v": 6.6},
            "wg":   {"v": 10.8},
        },
        "time": {
            "s":   "2026-04-05 09:00:00",
            "tz":  "-04:00",
            "v":   1775379600,
            "iso": "2026-04-05T09:00:00-04:00",
        },
        "forecast": {
            "daily": {
                "pm10": [
                    {"avg": 9, "day": "2026-04-03", "max": 13, "min": 3},
                    {"avg": 6, "day": "2026-04-04", "max": 12, "min": 3},
                    {"avg": 3, "day": "2026-04-05", "max": 6,  "min": 2},
                ],
                "pm25": [
                    {"avg": 27, "day": "2026-04-03", "max": 47, "min": 10},
                    {"avg": 22, "day": "2026-04-04", "max": 43, "min": 13},
                    {"avg": 13, "day": "2026-04-05", "max": 38, "min": 4},
                    {"avg": 18, "day": "2026-04-06", "max": 30, "min": 3},
                ],
                "uvi": [
                    {"avg": 0, "day": "2026-04-03", "max": 4, "min": 0},
                    {"avg": 0, "day": "2026-04-04", "max": 3, "min": 0},
                    {"avg": 0, "day": "2026-04-05", "max": 3, "min": 0},
                ],
            }
        },
        "debug": {"sync": "2026-04-05T23:22:24+09:00"},
    }
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_response(json_data: dict, raise_for_status=None) -> MagicMock:
    """Return a MagicMock that behaves like a requests.Response."""
    mock = MagicMock()
    mock.json.return_value = json_data
    if raise_for_status:
        mock.raise_for_status.side_effect = raise_for_status
    else:
        mock.raise_for_status.return_value = None
    return mock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def service(monkeypatch):
    """AirQualityService with config.yaml read patched out."""
    monkeypatch.setattr(
        "services.aqicn_service.yaml.safe_load", lambda _: MOCK_CONFIG)
    with patch("builtins.open", mock_open()):
        return AirQualityService()


# ---------------------------------------------------------------------------
# Constructor tests
# ---------------------------------------------------------------------------

class TestInit:
    def test_init_loads_api_key(self, monkeypatch):
        monkeypatch.setattr(
            "services.aqicn_service.yaml.safe_load", lambda _: MOCK_CONFIG)
        with patch("builtins.open", mock_open()):
            svc = AirQualityService()
        assert svc.api_key == "test-key-123"

    def test_init_missing_config_file(self):
        """FileNotFoundError is caught; service is constructed without crashing."""
        with patch("builtins.open", side_effect=FileNotFoundError):
            svc = AirQualityService()
        # Service exists; api_key was never set (early return in __init__)
        assert not hasattr(svc, "api_key") or svc.api_key == ""


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------

class TestGetAirQualityHappyPath:
    def test_full_response(self, service, monkeypatch):
        monkeypatch.setattr(
            "services.aqicn_service.requests.get",
            lambda *a, **kw: _mock_response(FULL_API_RESPONSE),
        )
        result = service.get_air_quality(42.7375, -84.5361)

        assert isinstance(result, AirQualityData)
        assert result.aqi == 27
        assert result.dominentpol == "o3"

        assert isinstance(result.city, AirQualityCityData)
        assert result.city.name == "Lansing, Michigan, USA"
        assert result.city.url == "https://aqicn.org/city/usa/michigan/lansing"

        assert isinstance(result.iaqi, AirQualityCurrentMeasurementData)
        assert result.iaqi.pm25 == 5
        assert result.iaqi.o3 == 27.2
        assert result.iaqi.h == 80

        assert isinstance(result.time, AirQualityTimeData)
        assert result.time.s == "2026-04-05 09:00:00"
        assert result.time.tz == "-04:00"
        assert result.time.v == 1775379600
        assert result.time.iso == "2026-04-05T09:00:00-04:00"

        assert isinstance(result.forecast, AirQualityForecastData)
        assert isinstance(result.forecast.daily, AirQualityDailyForecastData)
        assert len(result.forecast.daily.pm25) == 4
        assert result.forecast.daily.pm25[0].avg == 27
        assert len(result.forecast.daily.pm10) == 3
        assert len(result.forecast.daily.uvi) == 3

    def test_missing_forecast(self, service, monkeypatch):
        data = copy.deepcopy(FULL_API_RESPONSE)
        del data["data"]["forecast"]
        monkeypatch.setattr(
            "services.aqicn_service.requests.get",
            lambda *a, **kw: _mock_response(data),
        )
        result = service.get_air_quality(42.7375, -84.5361)
        assert result is not None
        assert result.forecast is None

    def test_missing_iaqi(self, service, monkeypatch):
        data = copy.deepcopy(FULL_API_RESPONSE)
        del data["data"]["iaqi"]
        monkeypatch.setattr(
            "services.aqicn_service.requests.get",
            lambda *a, **kw: _mock_response(data),
        )
        result = service.get_air_quality(42.7375, -84.5361)
        assert result is not None
        assert result.iaqi is None

    def test_missing_city(self, service, monkeypatch):
        data = copy.deepcopy(FULL_API_RESPONSE)
        del data["data"]["city"]
        monkeypatch.setattr(
            "services.aqicn_service.requests.get",
            lambda *a, **kw: _mock_response(data),
        )
        result = service.get_air_quality(42.7375, -84.5361)
        assert result is not None
        assert result.city is None


# ---------------------------------------------------------------------------
# API-level error tests
# ---------------------------------------------------------------------------

class TestGetAirQualityApiErrors:
    def test_missing_data_key(self, service, monkeypatch):
        monkeypatch.setattr(
            "services.aqicn_service.requests.get",
            lambda *a, **kw: _mock_response({"status": "ok"}),
        )
        assert service.get_air_quality(42.7375, -84.5361) is None

    def test_null_data_value(self, service, monkeypatch):
        monkeypatch.setattr(
            "services.aqicn_service.requests.get",
            lambda *a, **kw: _mock_response({"status": "ok", "data": None}),
        )
        assert service.get_air_quality(42.7375, -84.5361) is None


# ---------------------------------------------------------------------------
# Network / HTTP error tests
# ---------------------------------------------------------------------------

class TestGetAirQualityNetworkErrors:
    def test_timeout(self, service, monkeypatch):
        mock = MagicMock(side_effect=requests.exceptions.Timeout)
        monkeypatch.setattr("services.aqicn_service.requests.get", mock)
        assert service.get_air_quality(42.7375, -84.5361) is None

    def test_http_error_4xx(self, service, monkeypatch):
        resp = _mock_response(
            {},
            raise_for_status=requests.exceptions.HTTPError(
                response=MagicMock(status_code=403)),
        )
        monkeypatch.setattr(
            "services.aqicn_service.requests.get", lambda *a, **kw: resp
        )
        assert service.get_air_quality(42.7375, -84.5361) is None

    def test_http_error_5xx(self, service, monkeypatch):
        resp = _mock_response(
            {},
            raise_for_status=requests.exceptions.HTTPError(
                response=MagicMock(status_code=500)),
        )
        monkeypatch.setattr(
            "services.aqicn_service.requests.get", lambda *a, **kw: resp
        )
        assert service.get_air_quality(42.7375, -84.5361) is None

    def test_request_exception(self, service, monkeypatch):
        mock = MagicMock(
            side_effect=requests.exceptions.RequestException("connection refused"))
        monkeypatch.setattr("services.aqicn_service.requests.get", mock)
        assert service.get_air_quality(42.7375, -84.5361) is None


# ---------------------------------------------------------------------------
# URL / parameter construction tests
# ---------------------------------------------------------------------------

class TestRequestConstruction:
    def test_request_url_and_token(self, service, monkeypatch):
        captured = {}

        def fake_get(url, params=None, timeout=None):
            captured["url"] = url
            captured["params"] = params
            return _mock_response(FULL_API_RESPONSE)

        monkeypatch.setattr("services.aqicn_service.requests.get", fake_get)
        service.get_air_quality(42.7375, -84.5361)

        assert captured["url"] == "https://api.waqi.info/feed/geo:@42.7375;-84.5361"
        assert captured["params"] == {"token": "test-key-123"}
