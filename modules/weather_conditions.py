from core.command_dispatcher import CommandData
from interfaces.bot_module import BotModule
from services.meshtastic_service import TO_SEND_TOPIC, TextToSend
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
            return
        self.logger.info(
            "EVENT TRIGGERED: received weather conditions request event with data %s", data)
        if data.sender_id is None or (data.receiver_id is None and data.channel is None):
            self.logger.warning(
                "Weather command is missing essential message data")
            return
        # Geocode query into coordinates
        arguments = data.parameters
        if arguments is None or len(arguments) <= 0:
            self._send_message("You must provide a location.", data)
            return
        query = ' '.join(arguments)
        coords = self.geo_service.get_coords(query)
        if coords is None:
            self._send_message(
                "Unable to identify the location for your query.", data)
            return
        zone = self.api_service.get_zone(coords.latitude, coords.longitude)
        if zone is None:
            self._send_message(
                "Unable to identify the location for your query.", data)
            return
        conditions = self.api_service.get_conditions(zone)
        if conditions is None:
            self._send_message(
                "Unable to lookup the conditions for that location.", data)
            return

        conditions_summary = ""
        separater = ""
        if conditions.location is not None:
            conditions_summary = "Condititions from " + conditions.location + ":\n"
        if conditions.description is not None:
            conditions_summary = conditions_summary + separater + conditions.description
            separater = ". "
        if conditions.temperature is not None:
            conditions_summary = conditions_summary + separater + \
                "Temperature: " + \
                self._convert_num(conditions.temperature) + "°"
            separater = ", "
        if conditions.wind_chill is not None:
            conditions_summary = conditions_summary + separater + \
                "Wind Chill: " + self._convert_num(conditions.wind_chill) + "°"
            separater = ", "
        if conditions.heat_index is not None:
            conditions_summary = conditions_summary + separater + \
                "Heat Index: " + self._convert_num(conditions.heat_index) + "°"
            separater = ", "
        if conditions.humidity is not None:
            conditions_summary = conditions_summary + separater + \
                "Humidity: " + self._convert_num(conditions.humidity) + "%"
            separater = ", "
        if conditions.wind_speed is not None:
            conditions_summary = conditions_summary + separater + \
                "Wind: " + self._convert_num(conditions.wind_speed) + " m/h"
            separater = ", "
        if conditions.pressure is not None:
            conditions_summary = conditions_summary + separater + \
                "Pressure: " + self._convert_num(conditions.pressure)
            separater = ", "
        if conditions.precipitation is not None:
            conditions_summary = conditions_summary + separater + "Precipitation: " + \
                self._convert_num(conditions.precipitation) + " in"

        self._send_message(conditions_summary, data)

    def _convert_num(self, number) -> str:
        return f"{number:.1f}"

    def _send_message(self, message: str, command_data: CommandData):
        from_id = command_data.sender_id
        to_id = command_data.receiver_id
        channel_num = command_data.channel
        if from_id is not None and to_id == self.my_node_id:
            message_data = TextToSend(
                message,
                from_id,
                None,
                False
            )
            self.logger.info(
                "Weather command responding with payload: %s", message_data)
            self.event_bus.publish(TO_SEND_TOPIC, message_data)
        elif channel_num is not None and to_id == "^all":
            message_data = TextToSend(
                message,
                None,
                channel_num,
                False
            )
            self.logger.info(
                "Weather command responding with payload: %s", message_data)
            self.event_bus.publish(TO_SEND_TOPIC, message_data)
        else:
            self.logger.warning("Unable to handle weather command!")
