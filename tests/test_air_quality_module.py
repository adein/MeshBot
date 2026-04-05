"""
Tests for modules/air_quality.py

All external dependencies (API calls, geocoding, filesystem) are mocked.
"""

import pytest
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from models.air_quality import (
    AirQualityData,
    AirQualityCityData,
    AirQualityForecastData,
    AirQualityDailyForecastData,
    AirQualityForecastItemData,
)
from models.command import CommandData
from models.location import GpsLocation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_command(parameters=None, sender_id="!abc123", receiver_id=None,
                  channel=1, is_dm=False) -> CommandData:
    return CommandData(
        sender_id=sender_id,
        receiver_id=receiver_id,
        parameters=parameters,
        raw_message=" ".join(parameters) if parameters else "",
        channel=channel,
        rx_time=0,
        rx_snr=None,
        hops_away=None,
        via_mqtt=False,
        is_dm=is_dm,
    )


def _make_air_quality(aqi=42, city_name="Test City", pm25_avg=15, pm10_avg=8,
                      today="2026-04-05") -> AirQualityData:
    forecast_item_pm25 = AirQualityForecastItemData(avg=pm25_avg, day=today, max=30, min=5)
    forecast_item_pm10 = AirQualityForecastItemData(avg=pm10_avg, day=today, max=20, min=2)
    daily = AirQualityDailyForecastData(
        pm25=[forecast_item_pm25],
        pm10=[forecast_item_pm10],
        uvi=[],
    )
    return AirQualityData(
        aqi=aqi,
        city=AirQualityCityData(name=city_name, url=None),
        dominentpol="pm25",
        iaqi=None,
        time=None,
        forecast=AirQualityForecastData(daily=daily),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def module():
    """AirQuality module with all external dependencies mocked out."""
    config = {"enabled": True, "dm_only": False}
    root_config = {}
    mock_mesh = MagicMock()
    mock_bus = MagicMock()
    global_services = {"mesh": mock_mesh, "bus": mock_bus, "db": MagicMock()}

    with patch("modules.air_quality.AirQualityService"), \
         patch("modules.air_quality.PositionstackGeocodeService"):
        from modules.air_quality import AirQuality
        m = AirQuality("AirQuality", config, root_config, global_services, "!node1")

    m.mesh_service = mock_mesh
    m.local_tz = ZoneInfo("America/Detroit")
    return m


# ---------------------------------------------------------------------------
# AQI description / emoji helpers
# ---------------------------------------------------------------------------

class TestAqiDescription:
    @pytest.mark.parametrize("aqi,expected", [
        (0,   "Good"),
        (50,  "Good"),
        (51,  "Moderate"),
        (100, "Moderate"),
        (101, "Unhealthy for Sensitive Groups"),
        (150, "Unhealthy for Sensitive Groups"),
        (151, "Unhealthy"),
        (200, "Unhealthy"),
        (201, "Very Unhealthy"),
        (300, "Very Unhealthy"),
        (301, "Hazardous"),
        (500, "Hazardous"),
    ])
    def test_description_boundaries(self, module, aqi, expected):
        assert module._get_aqi_description(aqi) == expected


class TestAqiEmoji:
    @pytest.mark.parametrize("aqi,expected", [
        (25,  "🟢"),
        (75,  "🟡"),
        (125, "🟠"),
        (175, "🔴"),
        (250, "🟣"),
        (400, "🟤"),
    ])
    def test_emoji_ranges(self, module, aqi, expected):
        assert module._get_aqi_emoji(aqi) == expected


# ---------------------------------------------------------------------------
# Forecast summary
# ---------------------------------------------------------------------------

class TestForecastSummary:
    def test_returns_today_forecast(self, module):
        today = "2026-04-05"
        module.local_tz = ZoneInfo("America/Detroit")
        daily = AirQualityDailyForecastData(
            pm25=[AirQualityForecastItemData(avg=35, day=today, max=50, min=10)],
            pm10=[AirQualityForecastItemData(avg=12, day=today, max=20, min=5)],
            uvi=[],
        )
        with patch("modules.air_quality.datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = today
            summary = module._get_todays_forecast_summary(daily)

        assert "PM2.5" in summary
        assert "35" in summary
        assert "PM10" in summary
        assert "12" in summary

    def test_no_matching_date_returns_empty(self, module):
        daily = AirQualityDailyForecastData(
            pm25=[AirQualityForecastItemData(avg=35, day="2026-01-01", max=50, min=10)],
            pm10=[AirQualityForecastItemData(avg=12, day="2026-01-01", max=20, min=5)],
            uvi=[],
        )
        with patch("modules.air_quality.datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = "2026-04-05"
            summary = module._get_todays_forecast_summary(daily)

        assert summary == ""

    def test_none_pm25_skipped(self, module):
        today = "2026-04-05"
        daily = AirQualityDailyForecastData(
            pm25=None,
            pm10=[AirQualityForecastItemData(avg=8, day=today, max=15, min=3)],
            uvi=[],
        )
        with patch("modules.air_quality.datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = today
            summary = module._get_todays_forecast_summary(daily)

        assert "PM2.5" not in summary
        assert "PM10" in summary


# ---------------------------------------------------------------------------
# Handle air quality request — guard clauses
# ---------------------------------------------------------------------------

class TestHandleAirQualityRequestGuards:
    def test_disabled_module_does_nothing(self, module):
        module.config = {"enabled": False}
        cmd = _make_command(["Detroit"])
        module._handle_air_quality_request(cmd)
        module.mesh_service.send_reply.assert_not_called()

    def test_missing_sender_id_does_nothing(self, module):
        cmd = _make_command(["Detroit"])
        cmd = CommandData(
            sender_id=None,
            receiver_id=None,
            parameters=["Detroit"],
            raw_message="Detroit",
            channel=1,
            rx_time=0,
            rx_snr=None,
            hops_away=None,
            via_mqtt=False,
            is_dm=False,
        )
        module._handle_air_quality_request(cmd)
        module.mesh_service.send_reply.assert_not_called()

    def test_dm_only_rejects_channel_message(self, module):
        module.config = {"enabled": True, "dm_only": True}
        cmd = _make_command(["Detroit"], is_dm=False)
        module._handle_air_quality_request(cmd)
        module.mesh_service.send_reply.assert_not_called()

    def test_no_arguments_sends_help_message(self, module):
        cmd = _make_command([])
        module._handle_air_quality_request(cmd)
        module.mesh_service.send_reply.assert_called_once()
        reply = module.mesh_service.send_reply.call_args[0][0]
        assert "location" in reply.lower()

    def test_geocode_failure_sends_error(self, module):
        module.geo_service = MagicMock()
        module.geo_service.get_coords.return_value = None
        cmd = _make_command(["nowhere"])
        module._handle_air_quality_request(cmd)
        reply = module.mesh_service.send_reply.call_args[0][0]
        assert "location" in reply.lower()

    def test_api_failure_sends_error(self, module):
        module.geo_service = MagicMock()
        module.geo_service.get_coords.return_value = GpsLocation(latitude=42.0, longitude=-84.0)
        module.api_service = MagicMock()
        module.api_service.get_air_quality.return_value = None
        with patch("modules.air_quality.TimezoneFinder") as mock_tf:
            mock_tf.return_value.timezone_at.return_value = "America/Detroit"
            cmd = _make_command(["Detroit"])
            module._handle_air_quality_request(cmd)
        reply = module.mesh_service.send_reply.call_args[0][0]
        assert "unable" in reply.lower()


# ---------------------------------------------------------------------------
# Handle air quality request — happy path
# ---------------------------------------------------------------------------

class TestHandleAirQualityRequestHappyPath:
    def _setup(self, module, aqi=42, city_name="Detroit, MI", today="2026-04-05"):
        module.geo_service = MagicMock()
        module.geo_service.get_coords.return_value = GpsLocation(latitude=42.33, longitude=-83.04)
        module.api_service = MagicMock()
        module.api_service.get_air_quality.return_value = _make_air_quality(
            aqi=aqi, city_name=city_name, today=today)

    def test_reply_contains_city_and_aqi(self, module):
        self._setup(module, aqi=42, city_name="Detroit, MI")
        with patch("modules.air_quality.TimezoneFinder") as mock_tf, \
             patch("modules.air_quality.datetime") as mock_dt:
            mock_tf.return_value.timezone_at.return_value = "America/Detroit"
            mock_dt.now.return_value.strftime.return_value = "2026-04-05"
            cmd = _make_command(["Detroit"])
            module._handle_air_quality_request(cmd)

        reply = module.mesh_service.send_reply.call_args[0][0]
        assert "Detroit, MI" in reply
        assert "42" in reply

    def test_good_aqi_description(self, module):
        self._setup(module, aqi=25)
        with patch("modules.air_quality.TimezoneFinder") as mock_tf, \
             patch("modules.air_quality.datetime") as mock_dt:
            mock_tf.return_value.timezone_at.return_value = "America/Detroit"
            mock_dt.now.return_value.strftime.return_value = "2026-04-05"
            cmd = _make_command(["Detroit"])
            module._handle_air_quality_request(cmd)

        reply = module.mesh_service.send_reply.call_args[0][0]
        assert "Good" in reply

    def test_unhealthy_aqi_description(self, module):
        self._setup(module, aqi=175)
        with patch("modules.air_quality.TimezoneFinder") as mock_tf, \
             patch("modules.air_quality.datetime") as mock_dt:
            mock_tf.return_value.timezone_at.return_value = "America/Detroit"
            mock_dt.now.return_value.strftime.return_value = "2026-04-05"
            cmd = _make_command(["Detroit"])
            module._handle_air_quality_request(cmd)

        reply = module.mesh_service.send_reply.call_args[0][0]
        assert "Unhealthy" in reply

    def test_reply_contains_forecast(self, module):
        self._setup(module, aqi=42, today="2026-04-05")
        with patch("modules.air_quality.TimezoneFinder") as mock_tf, \
             patch("modules.air_quality.datetime") as mock_dt:
            mock_tf.return_value.timezone_at.return_value = "America/Detroit"
            mock_dt.now.return_value.strftime.return_value = "2026-04-05"
            cmd = _make_command(["Detroit"])
            module._handle_air_quality_request(cmd)

        reply = module.mesh_service.send_reply.call_args[0][0]
        assert "PM2.5" in reply
        assert "PM10" in reply

    def test_no_city_name_still_replies(self, module):
        module.geo_service = MagicMock()
        module.geo_service.get_coords.return_value = GpsLocation(latitude=42.33, longitude=-83.04)
        module.api_service = MagicMock()
        aq = _make_air_quality(aqi=55, city_name=None)
        aq.city.name = None
        module.api_service.get_air_quality.return_value = aq

        with patch("modules.air_quality.TimezoneFinder") as mock_tf, \
             patch("modules.air_quality.datetime") as mock_dt:
            mock_tf.return_value.timezone_at.return_value = "America/Detroit"
            mock_dt.now.return_value.strftime.return_value = "2026-04-05"
            cmd = _make_command(["42.33", "-83.04"])
            module._handle_air_quality_request(cmd)

        module.mesh_service.send_reply.assert_called_once()
        reply = module.mesh_service.send_reply.call_args[0][0]
        assert "55" in reply

    def test_dm_only_allows_dm(self, module):
        module.config = {"enabled": True, "dm_only": True}
        self._setup(module, aqi=30)
        with patch("modules.air_quality.TimezoneFinder") as mock_tf, \
             patch("modules.air_quality.datetime") as mock_dt:
            mock_tf.return_value.timezone_at.return_value = "America/Detroit"
            mock_dt.now.return_value.strftime.return_value = "2026-04-05"
            cmd = _make_command(["Detroit"], is_dm=True, receiver_id="!node1")
            module._handle_air_quality_request(cmd)

        module.mesh_service.send_reply.assert_called_once()
