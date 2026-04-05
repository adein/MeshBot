from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from timezonefinder import TimezoneFinder

from interfaces.bot_module import BotModule
from models.command import CommandData
from models.location import GpsLocation
from models.air_quality import AirQualityDailyForecastData, AirQualityForecastItemData
from services.aqicn_service import AirQualityService
from services.positionstack_geocode_service import PositionstackGeocodeService


class AirQuality(BotModule):
    """
    Module to respond to 'airquality' commands with air quality information for a location.
    """

    local_tz: ZoneInfo | None = None

    def __init__(self, name: str, config, root_config, global_services: dict, my_node: str):
        super().__init__(name, config, root_config, global_services, my_node)
        # Initialize the geocode service
        self.geo_service = PositionstackGeocodeService()
        # Initialize the air quality service
        self.api_service = AirQualityService()
        # Listen to air quality events
        if self.event_bus:
            self.event_bus.subscribe(
                "bot.command.air_quality", self._handle_air_quality_request)

    def execute(self):
        # Triggered, so this is empty
        pass

    def _handle_air_quality_request(self, data: CommandData):
        if not self.is_enabled():
            self.logger.warning(
                "Air quality command triggered, but module is disabled.")
            return
        if data.sender_id is None or (data.receiver_id is None and data.channel is None):
            self.logger.debug(
                "Air quality command is missing essential message data")
            return
        if self.is_dm_only() and not data.is_dm:
            self.logger.debug(
                "Air quality command received in non-DM, but module is DM-only.")
            return
        # Geocode query into coordinates
        arguments = data.parameters
        self.logger.info(
            "Handling air quality command with arguments: %s", arguments)
        if arguments is None or len(arguments) <= 0:
            self.mesh_service.send_reply("You must provide a location.", data)
            return
        query = ' '.join(arguments)
        coords: GpsLocation | None = self.geo_service.get_coords(query)
        if coords is None:
            self.mesh_service.send_reply(
                "Unable to identify the location for your query.", data)
            return
        localzone = self._get_time_zone(coords.latitude, coords.longitude)
        if localzone is not None:
            tz_string = self.config.get('local_timezone', localzone)
        else:
            tz_string = self.config.get(
                'local_timezone', "America/Detroit")
        self.local_tz = ZoneInfo(tz_string)
        air_quality = self.api_service.get_air_quality(
            coords.latitude, coords.longitude)
        if air_quality is None:
            self.mesh_service.send_reply(
                "Unable to retrieve air quality data for that location.", data)
            return
        summary = "Air Quality"
        if air_quality.city is not None and air_quality.city.name is not None:
            location = air_quality.city.name.removesuffix(", USA")
            summary += f" in {location}:"
        else:
            summary += ":"
        if air_quality.aqi is not None:
            description = self.api_service.get_aqi_description(air_quality.aqi)
            emoji = self.api_service.get_aqi_emoji(air_quality.aqi)
            summary += f" {description} {air_quality.aqi} {emoji}\n"
        else:
            summary += " Unknown\n"
        if air_quality.forecast is not None and air_quality.forecast.daily is not None:
            forecast_summary = self.api_service.get_todays_forecast_summary(
                self.local_tz, air_quality.forecast.daily)
            if len(forecast_summary) > 0:
                summary += forecast_summary
        if len(summary) <= 0:
            self.mesh_service.send_reply(
                "Error processing air quality information for that location.", data)
            return
        self.mesh_service.send_reply(summary, data)

    def _get_time_zone(self, latitude: float, longitude: float) -> str | None:
        tf = TimezoneFinder()
        time_zone = tf.timezone_at(lat=latitude, lng=longitude)
        return time_zone
