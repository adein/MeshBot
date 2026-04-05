"""
Tests for modules/local_aqi_alerts.py

All external dependencies (API calls, filesystem, sleep) are mocked.
"""

import pytest
from unittest.mock import MagicMock, call, patch
from zoneinfo import ZoneInfo

from models.air_quality import (
    AirQualityData,
    AirQualityCityData,
    AirQualityForecastData,
    AirQualityDailyForecastData,
    AirQualityForecastItemData,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_air_quality(aqi=75, city_name="Test City", with_forecast=True,
                      today="2026-04-05") -> AirQualityData:
    forecast = None
    if with_forecast:
        daily = AirQualityDailyForecastData(
            pm25=[AirQualityForecastItemData(
                avg=35, day=today, max=50, min=10)],
            pm10=[AirQualityForecastItemData(
                avg=12, day=today, max=20, min=5)],
            uvi=[],
        )
        forecast = AirQualityForecastData(daily=daily)
    return AirQualityData(
        aqi=aqi,
        city=AirQualityCityData(
            name=city_name, url=None) if city_name else None,
        dominentpol="pm25",
        iaqi=None,
        time=None,
        forecast=forecast,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def module():
    """AirQualityChecker with all external dependencies mocked out."""
    config = {
        "enabled": True,
        "dm_only": False,
        "channels": [1, 2],
        "aqi_threshold": 51,
        "latitude": 42.33,
        "longitude": -83.04,
        "local_timezone": "America/Detroit",
    }
    root_config = {}
    mock_mesh = MagicMock()
    mock_bus = MagicMock()
    global_services = {"mesh": mock_mesh, "bus": mock_bus, "db": MagicMock()}

    with patch("modules.local_aqi_alerts.AirQualityService"):
        from modules.local_aqi_alerts import AirQualityChecker
        m = AirQualityChecker("AirQualityChecker", config, root_config,
                              global_services, "!node1")

    m.mesh_service = mock_mesh
    m.active_alert_level = None
    return m


# ---------------------------------------------------------------------------
# Constructor tests
# ---------------------------------------------------------------------------

class TestInit:
    def test_loads_config_values(self, module):
        assert module.channels == [1, 2]
        assert module.aqi_threshold == 51
        assert module.latitude == 42.33
        assert module.longitude == -83.04

    def test_missing_latitude_logs_error(self):
        config = {"enabled": True, "channels": [1], "aqi_threshold": 51,
                  "latitude": None, "longitude": -83.04}
        with patch("modules.local_aqi_alerts.AirQualityService"):
            from modules.local_aqi_alerts import AirQualityChecker
            m = AirQualityChecker("AQI", config, {}, {}, "!node1")
            assert m.latitude is None

    def test_missing_threshold_logs_error(self):
        config = {"enabled": True, "channels": [1],
                  "latitude": 42.33, "longitude": -83.04}
        with patch("modules.local_aqi_alerts.AirQualityService"):
            from modules.local_aqi_alerts import AirQualityChecker
            m = AirQualityChecker("AQI", config, {}, {}, "!node1")
            assert m.aqi_threshold is None


# ---------------------------------------------------------------------------
# execute — guard clauses
# ---------------------------------------------------------------------------

class TestExecuteGuards:
    def test_disabled_does_nothing(self, module):
        module.config = {**module.config, "enabled": False}
        module.execute()
        module.api_service.get_air_quality.assert_not_called()

    def test_missing_latitude_returns_early(self, module):
        module.latitude = None
        module.execute()
        module.api_service.get_air_quality.assert_not_called()

    def test_missing_longitude_returns_early(self, module):
        module.longitude = None
        module.execute()
        module.api_service.get_air_quality.assert_not_called()

    def test_missing_threshold_returns_early(self, module):
        module.aqi_threshold = None
        module.execute()
        module.api_service.get_air_quality.assert_not_called()

    def test_api_returns_none_returns_early(self, module):
        module.api_service.get_air_quality.return_value = None
        module.execute()
        module.mesh_service.send_text.assert_not_called()

    def test_api_returns_none_aqi_returns_early(self, module):
        data = _make_air_quality(aqi=None)
        data.aqi = None
        module.api_service.get_air_quality.return_value = data
        module.execute()
        module.mesh_service.send_text.assert_not_called()

    def test_aqi_below_threshold_clears_active_level(self, module):
        module.active_alert_level = 2
        module.api_service.get_air_quality.return_value = _make_air_quality(
            aqi=30)
        module.execute()
        assert module.active_alert_level is None
        module.mesh_service.send_text.assert_not_called()

    def test_aqi_level_not_increased_sends_no_alert(self, module):
        module.active_alert_level = 1  # Moderate
        module.api_service.get_air_quality.return_value = _make_air_quality(
            aqi=75)
        module.api_service.get_aqi_level.return_value = 1
        with patch("modules.local_aqi_alerts.TimezoneFinder") as mock_tf:
            mock_tf.return_value.timezone_at.return_value = "America/Detroit"
            module.execute()
        module.mesh_service.send_text.assert_not_called()
        assert module.active_alert_level == 1  # unchanged


# ---------------------------------------------------------------------------
# execute — happy path
# ---------------------------------------------------------------------------

class TestExecuteHappyPath:
    def test_sends_alert_to_all_channels(self, module):
        module.api_service.get_air_quality.return_value = _make_air_quality(
            aqi=120)
        module.api_service.get_aqi_level.return_value = 2
        module.api_service.get_todays_forecast_summary.return_value = ""
        with patch("modules.local_aqi_alerts.TimezoneFinder") as mock_tf, \
                patch("modules.local_aqi_alerts.time") as mock_time:
            mock_tf.return_value.timezone_at.return_value = "America/Detroit"
            module.execute()

        assert module.mesh_service.send_text.call_count == 2
        mock_time.sleep.assert_called()

    def test_active_alert_level_updated(self, module):
        module.active_alert_level = None
        module.api_service.get_air_quality.return_value = _make_air_quality(
            aqi=120)
        module.api_service.get_aqi_level.return_value = 2
        module.api_service.get_todays_forecast_summary.return_value = ""
        with patch("modules.local_aqi_alerts.TimezoneFinder") as mock_tf, \
                patch("modules.local_aqi_alerts.time"):
            mock_tf.return_value.timezone_at.return_value = "America/Detroit"
            module.execute()
        assert module.active_alert_level == 2

    def test_higher_level_sends_new_alert(self, module):
        module.active_alert_level = 1
        module.api_service.get_air_quality.return_value = _make_air_quality(
            aqi=160)
        module.api_service.get_aqi_level.return_value = 3
        module.api_service.get_todays_forecast_summary.return_value = ""
        with patch("modules.local_aqi_alerts.TimezoneFinder") as mock_tf, \
                patch("modules.local_aqi_alerts.time"):
            mock_tf.return_value.timezone_at.return_value = "America/Detroit"
            module.execute()
        module.mesh_service.send_text.assert_called()
        assert module.active_alert_level == 3

    def test_timezone_fallback_when_not_found(self, module):
        module.config = {**module.config, "local_timezone": "America/Detroit"}
        module.api_service.get_air_quality.return_value = _make_air_quality(
            aqi=120)
        module.api_service.get_aqi_level.return_value = 2
        module.api_service.get_todays_forecast_summary.return_value = ""
        with patch("modules.local_aqi_alerts.TimezoneFinder") as mock_tf, \
                patch("modules.local_aqi_alerts.time"):
            mock_tf.return_value.timezone_at.return_value = None  # not found
            module.execute()
        module.mesh_service.send_text.assert_called()


# ---------------------------------------------------------------------------
# _generate_alert
# ---------------------------------------------------------------------------

class TestGenerateAlert:
    def test_none_aqi_returns_none(self, module):
        data = _make_air_quality(aqi=None)
        data.aqi = None
        assert module._generate_alert(
            data, ZoneInfo("America/Detroit")) is None

    def test_includes_city_name(self, module):
        module.api_service.get_aqi_description.return_value = "Unhealthy for Sensitive Groups"
        module.api_service.get_aqi_emoji.return_value = "🟠"
        module.api_service.get_todays_forecast_summary.return_value = ""
        data = _make_air_quality(aqi=120, city_name="Lansing, MI")
        result = module._generate_alert(data, ZoneInfo("America/Detroit"))
        assert "Lansing, MI" in result
        assert "120" in result

    def test_no_city_name_uses_generic_header(self, module):
        module.api_service.get_aqi_description.return_value = "Unhealthy for Sensitive Groups"
        module.api_service.get_aqi_emoji.return_value = "🟠"
        module.api_service.get_todays_forecast_summary.return_value = ""
        data = _make_air_quality(aqi=120, city_name=None)
        result = module._generate_alert(data, ZoneInfo("America/Detroit"))
        assert result is not None
        assert "Alert" in result
        assert "120" in result

    def test_includes_forecast_when_present(self, module):
        module.api_service.get_aqi_description.return_value = "Unhealthy"
        module.api_service.get_aqi_emoji.return_value = "🔴"
        module.api_service.get_todays_forecast_summary.return_value = (
            "PM2.5: Unhealthy 160 🔴 (min 120, max 200)\n"
        )
        data = _make_air_quality(aqi=160, with_forecast=True)
        result = module._generate_alert(data, ZoneInfo("America/Detroit"))
        assert "PM2.5" in result

    def test_no_forecast_omits_forecast_section(self, module):
        module.api_service.get_aqi_description.return_value = "Unhealthy"
        module.api_service.get_aqi_emoji.return_value = "🔴"
        data = _make_air_quality(aqi=160, with_forecast=False)
        result = module._generate_alert(data, ZoneInfo("America/Detroit"))
        assert result is not None
        module.api_service.get_todays_forecast_summary.assert_not_called()


# ---------------------------------------------------------------------------
# _send_message
# ---------------------------------------------------------------------------

class TestSendMessage:
    def test_sends_to_each_channel(self, module):
        with patch("modules.local_aqi_alerts.time") as mock_time:
            module._send_message("Test alert")
        calls = module.mesh_service.send_text.call_args_list
        assert len(calls) == 2
        assert calls[0] == call("Test alert", to_channel_number=1)
        assert calls[1] == call("Test alert", to_channel_number=2)

    def test_sleeps_between_messages(self, module):
        with patch("modules.local_aqi_alerts.time") as mock_time:
            module._send_message("Test alert")
        assert mock_time.sleep.call_count == 2
