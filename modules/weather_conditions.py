from core.command_dispatcher import CommandData
from interfaces.bot_module import BotModule
from services.positionstack_geocode_service import PositionstackGeocodeService
from services.nws_weather_service import NwsWeatherService


class WeatherConditions(BotModule):
    """
    Module to respond to 'weather' commands with NWS weather conditions information.
    """

    def __init__(self, name: str, config, global_services: dict, my_node: str):
        super().__init__(name, config, global_services, my_node)
        # Initialize the geocode service
        self.geo_service = PositionstackGeocodeService()
        # Initialize the weather service
        self.api_service = NwsWeatherService()
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
        # Geocode query into coordinates
        arguments = data.parameters
        self.logger.info(
            "Handling weather command with arguments: %s", arguments)
        if arguments is None or len(arguments) <= 0:
            self.mesh_service.send_reply("You must provide a location.", data)
            return
        query = ' '.join(arguments)
        coords = self.geo_service.get_coords(query)
        if coords is None:
            self.mesh_service.send_reply(
                "Unable to identify the location for your query.", data)
            return
        zone = self.api_service.get_zone(coords.latitude, coords.longitude)
        if zone is None:
            self.mesh_service.send_reply(
                "Unable to identify the location for your query.", data)
            return
        conditions = self.api_service.get_conditions(zone)
        if conditions is None:
            self.mesh_service.send_reply(
                "Unable to lookup the conditions for that location.", data)
            return

        conditions_summary = ""
        # First row: Location
        if conditions.location is not None:
            conditions_summary = "Condititions at " + conditions.location + ":\n"
        else:
            conditions_summary = "Current condititions:\n"
        # Second row: Summary
        if conditions.description is not None:
            description_emoji = self._get_conditions_emoji(
                conditions.description)
            conditions_summary = conditions_summary + \
                description_emoji + conditions.description
        # Third row: Temperature/etc
        separater = "\n"
        if conditions.temperature is not None:
            conditions_summary = conditions_summary + separater + \
                "🌡️ Temperature: " + \
                self._convert_num(conditions.temperature) + "°"
            separater = ", "
        if conditions.wind_chill is not None:
            conditions_summary = conditions_summary + separater + \
                "🥶 Wind Chill: " + \
                self._convert_num(conditions.wind_chill) + "°"
            separater = ", "
        if conditions.heat_index is not None:
            conditions_summary = conditions_summary + separater + \
                "🥵 Heat Index: " + \
                self._convert_num(conditions.heat_index) + "°"

        # Fourth row: Humidity/etc
        separater = "\n"
        if conditions.humidity is not None:
            conditions_summary = conditions_summary + separater + \
                "💧 Humidity: " + self._convert_num(conditions.humidity) + "%"
            separater = ", "
        if conditions.wind_speed is not None:
            conditions_summary = conditions_summary + separater + \
                "💨 Wind: " + self._convert_num(conditions.wind_speed) + " m/h"

        # Fifth row: Precipitation
        separater = "\n"
        if conditions.precipitation is not None:
            conditions_summary = conditions_summary + separater + "🌧️ Precipitation: " + \
                self._convert_num(conditions.precipitation) + ' "'

        self.mesh_service.send_reply(conditions_summary, data)

    def _convert_num(self, number) -> str:
        return f"{number:.1f}"

    def _get_conditions_emoji(self, conditions: str) -> str:
        conditions = conditions.lower()
        if "sunny" in conditions or "clear" in conditions:
            return "☀️ "
        elif "partly" in conditions or "cloudy" in conditions:
            return "⛅ "
        elif "cloud" in conditions or "overcast" in conditions:
            return "☁️ "
        elif "rain" in conditions or "drizzle" in conditions:
            return "🌧️ "
        elif "thunder" in conditions or "storm" in conditions:
            return "⛈️ "
        elif "snow" in conditions or "blizzard" in conditions:
            return "❄️ "
        elif "fog" in conditions or "mist" in conditions:
            return "🌫️️ "
        else:
            return ""
