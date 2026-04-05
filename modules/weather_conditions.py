from interfaces.bot_module import BotModule
from models.command import CommandData
from models.location import GpsLocation
from models.weather import WeatherConditionsData
from services.positionstack_geocode_service import PositionstackGeocodeService
from services.openmeteo_weather_service import OpenMeteoWeatherService
from utils.geo_utils import get_city_state_offline


class WeatherConditions(BotModule):
    """
    Module to respond to 'weather' commands with NWS weather conditions information.
    """

    def __init__(self, name: str, config, root_config, global_services: dict, my_node: str):
        super().__init__(name, config, root_config, global_services, my_node)
        # Initialize the geocode service
        self.geo_service = PositionstackGeocodeService()
        # Initialize the weather service
        self.api_service = OpenMeteoWeatherService()
        # Listen to weather summary events
        if self.event_bus:
            self.event_bus.subscribe(
                "bot.command.weather", self._handle_weather_request)

    def execute(self):
        # Triggered, so this is empty
        pass

    def _handle_weather_request(self, data: CommandData):
        if not self.is_enabled():
            self.logger.warning(
                "Weather command triggered, but module is disabled.")
            return
        if data.sender_id is None or (data.receiver_id is None and data.channel is None):
            self.logger.debug(
                "Weather command is missing essential message data")
            return
        if self.is_dm_only() and not data.is_dm:
            self.logger.debug(
                "Weather command received in non-DM, but module is DM-only.")
            return
        # Geocode query into coordinates
        arguments = data.parameters
        self.logger.info(
            "Handling weather command with arguments: %s", arguments)
        if arguments is None or len(arguments) <= 0:
            self.mesh_service.send_reply("You must provide a location.", data)
            return
        query = ' '.join(arguments)
        coords: GpsLocation | None = self.geo_service.get_coords(query)
        if coords is None:
            self.mesh_service.send_reply(
                "Unable to identify the location for your query.", data)
            return
        conditions: WeatherConditionsData | None = self.api_service.get_conditions(
            coords.latitude, coords.longitude)
        if conditions is None:
            self.mesh_service.send_reply(
                "Unable to lookup the conditions for that location.", data)
            return
        location: str | None = get_city_state_offline(
            coords.latitude, coords.longitude)

        conditions_summary = ""
        # First row: Description of response
        if location is not None:
            conditions_summary = "Weather for " + location + ":\n"
        else:
            conditions_summary = "Current weather:\n"
        # Second row: Summary
        if conditions.description is not None:
            conditions_summary = conditions_summary + \
                conditions.description
        # Third row: Temperature/etc
        separater = "\n"
        if conditions.temperature is not None:
            conditions_summary = conditions_summary + separater + \
                "🌡️ Temperature: " + \
                self._convert_num(conditions.temperature) + "°"
            separater = ", "
        if conditions.apparent_temperature is not None:
            conditions_summary = conditions_summary + separater + \
                "👤 Feels Like: " + \
                self._convert_num(conditions.apparent_temperature) + "°"

        # Fourth row: Wind
        separater = "\n"
        if conditions.wind_speed is not None:
            conditions_summary = conditions_summary + separater + \
                "🍃 Wind: " + self._convert_num(conditions.wind_speed) + " m/h"
            separater = ", "
        if conditions.wind_gusts is not None:
            conditions_summary = conditions_summary + separater + \
                "💨 Gusts: " + self._convert_num(conditions.wind_gusts) + " m/h"

        # Fifth row: Humidity and Precipitation
        separater = "\n"
        if conditions.humidity is not None:
            conditions_summary = conditions_summary + separater + \
                "💧 Humidity: " + self._convert_num(conditions.humidity) + "%"
            separater = ", "
        if conditions.precipitation is not None:
            conditions_summary = conditions_summary + separater + "🌧️ Precipitation: " + \
                self._convert_num(conditions.precipitation) + '"'

        self.mesh_service.send_reply(conditions_summary, data)

    def _convert_num(self, number) -> str:
        return f"{number:.1f}"
