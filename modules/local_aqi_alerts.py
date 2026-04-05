import time

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from timezonefinder import TimezoneFinder

from interfaces.bot_module import BotModule
from models.air_quality import AirQualityData
from services.aqicn_service import AirQualityService


class AirQualityChecker(BotModule):
    """
    Module to periodically check for air quality alerts and send them to channels.
    """

    active_alert_level: int | None = None

    def __init__(self, name: str, config, root_config, global_services: dict, my_node: str):
        super().__init__(name, config, root_config, global_services, my_node)
        # Initialize the service once when the module loads
        self.api_service = AirQualityService()
        self.channels: list[int] = self.config.get('channels', [])
        self.aqi_threshold: int = self.config.get('aqi_threshold', None)
        self.latitude: float = self.config.get('latitude', None)
        self.longitude: float = self.config.get('longitude', None)
        if self.latitude is None or self.longitude is None or self.aqi_threshold is None:
            self.logger.error(
                "Air Quality Checker missing required latitude, longitude, or threshold configuration!")

    def execute(self):
        if not self.is_enabled():
            self.logger.error(
                "Air Quality Checker triggered, but module is disabled. This shouldn't happen.")
            return
        if self.latitude is None or self.longitude is None or self.aqi_threshold is None:
            self.logger.error(
                "Air Quality Checker missing required latitude, longitude, or threshold configuration!")
            return
        data: AirQualityData | None = self.api_service.get_air_quality(
            self.latitude, self.longitude)
        if data is None or data.aqi is None:
            self.logger.error(
                "Air Quality Checker failed to get air quality data!")
            return
        if data.aqi < self.aqi_threshold:
            # Clear any active alert level if AQI is below threshold
            self.active_alert_level = None
            self.logger.debug(
                "Air Quality Checker: AQI %s is below threshold %s, no alert.", data.aqi, self.aqi_threshold)
            return
        aqi_level = self.api_service.get_aqi_level(data.aqi)
        if self.active_alert_level is not None and aqi_level <= self.active_alert_level:
            # AQI level has not increased, no new alert
            # Update active alert level even if not increased, to track changes
            self.active_alert_level = aqi_level
            self.logger.debug(
                "Air Quality Checker: AQI level %s has not increased from active alert level %s, no new alert.", aqi_level, self.active_alert_level)
            return
        self.active_alert_level = aqi_level
        localzone = self._get_time_zone(self.latitude, self.longitude)
        if localzone is not None:
            tz_string = self.config.get('local_timezone', localzone)
        else:
            tz_string = self.config.get(
                'local_timezone', "America/Detroit")
        local_tz = ZoneInfo(tz_string)
        alert = self._generate_alert(data, local_tz)
        if alert is not None:
            self._send_message(alert)
        else:
            self.logger.error(
                "Air Quality Checker was unable to generate alert message from data: %s", data)

    def _get_time_zone(self, latitude: float, longitude: float) -> str | None:
        tf = TimezoneFinder()
        time_zone = tf.timezone_at(lat=latitude, lng=longitude)
        return time_zone

    def _generate_alert(self, data: AirQualityData, local_tz: ZoneInfo) -> str | None:
        if data.aqi is None:
            return None
        aqi_description = self.api_service.get_aqi_description(data.aqi)
        aqi_emoji = self.api_service.get_aqi_emoji(data.aqi)
        summary = "Air Quality Alert: "
        if data.city is not None and data.city.name is not None:
            location = data.city.name.removesuffix(", USA")
            summary = f"Air Quality Alert for {location}: "
        summary += f"{aqi_emoji} {aqi_description} {data.aqi}"
        if data.forecast is not None and data.forecast.daily is not None:
            forecast_summary = self.api_service.get_todays_forecast_summary(
                local_tz, data.forecast.daily)
            if len(forecast_summary) > 0:
                summary += "\n" + forecast_summary
        return summary

    def _send_message(self, message: str):
        for channel in self.channels:
            self.mesh_service.send_text(message, to_channel_number=channel)
            time.sleep(4)
