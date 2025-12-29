from interfaces.bot_module import BotModule
from services.meshtastic_service import TextToSend
from services.positionstack_geocode_service import PositionstackGeocodeService
from services.nws_weather_service import NwsWeatherService

class WeatherForecast(BotModule):
    def __init__(self, name, config, global_services, my_node=None):
        super().__init__(name, config, global_services, my_node)
        # Initialize the geocode service
        self.geo_service = PositionstackGeocodeService()
        # Initialize the weather service
        self.api_service = NwsWeatherService()
        # Listen to weather summary events
        if self.event_bus:
            self.event_bus.subscribe("bot.command.forecast", self._handle_weather_request)

    def execute(self):
        # Triggered vs scheduled, so this is empty
        pass

    def _handle_weather_request(self, data):
        if not self.is_enabled():
            return
        self.logger.info(f"EVENT TRIGGERED: received weather forecast request event with data {data}")
        if data.sender_id is None or (data.receiver_id is None and data.channel is None):
            self.logger.warn(f"Forecast command is missing essential message data")
            return
        # Geocode query into coordinates
        arguments = data.parameters
        if arguments == None or len(arguments) <= 0:
            self._send_message("You must provide a location.", data)
            return
        query = ' '.join(arguments)
        coords = self.geo_service.get_coords(query)
        if coords == None:
            self._send_message("Unable to identify the location for your query.", data)
            return
        zone = self.api_service.get_zone(coords.latitude, coords.longitude)
        if zone == None:
            self._send_message("Unable to identify the location for your query.", data)
            return
        forecasts = self.api_service.get_forecasts(zone)
        if forecasts == None or len(forecasts) <= 0:
            self._send_message("Unable to lookup the conditions for that location.", data)
            return
        forecast_summary = ""
        for forecast in forecasts:
            fname = forecast.name
            desc = forecast.forecast
            if desc == None:
                continue
            if len(forecast_summary) == 0:
                if fname != None:
                    forecast_summary = fname + ": " + desc
                else:
                    forecast_summary = desc
            elif len(forecast_summary) < 200:
                forecast_summary = forecast_summary + "\n" + fname + ": " + desc
        if len(forecast_summary) <= 0:
            self._send_message("Unable to lookup the forecast for that location.", data)
            return
        self._send_message(forecast_summary, data)

    def _send_message(self, message, command_data):
        from_id = command_data.sender_id
        to_id = command_data.receiver_id
        channel_num = command_data.channel
        if from_id != None and to_id == self.my_node_id:
            message_data = TextToSend(
                    message,
                    from_id,
                    None,
                    False
            )
            self.logger.info(f"Forecast command responding with payload: {message_data}")
            self.event_bus.publish("meshtastic_service.to_send", message_data)
        elif channel_num != None and to_id == "^all":
            message_data = TextToSend(
                    message,
                    None,
                    channel_num,
                    False
            )
            self.logger.info(f"Forecast command responding with payload: {message_data}")
            self.event_bus.publish("meshtastic_service.to_send", message_data)
        else:
            self.logger.warn(f"Unable to handle forecast command!")
 
