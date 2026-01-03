from interfaces.bot_module import BotModule
from models.command import CommandData
from models.location import GpsLocation
from models.weather import WeatherForecast
from services.positionstack_geocode_service import PositionstackGeocodeService
from services.nws_weather_service import NwsWeatherService


class WeatherForecast(BotModule):
    """
    Module to respond to 'forecast' commands with NWS weather forecast information.
    """

    def __init__(self, name, config, root_config, global_services, my_node=None):
        super().__init__(name, config, root_config, global_services, my_node)
        # Initialize the geocode service
        self.geo_service = PositionstackGeocodeService()
        # Initialize the weather service
        self.api_service = NwsWeatherService()
        # Listen to weather summary events
        if self.event_bus:
            self.event_bus.subscribe(
                "bot.command.forecast", self._handle_weather_request)

    def execute(self):
        # Triggered vs scheduled, so this is empty
        pass

    def _handle_weather_request(self, data: CommandData):
        if not self.is_enabled():
            self.logger.warning(
                "Forecast command triggered, but module is disabled.")
            return
        if data.sender_id is None or (data.receiver_id is None and data.channel is None):
            self.logger.debug(
                "Forecast command is missing essential message data")
            return
        # Geocode query into coordinates
        arguments = data.parameters
        self.logger.info(
            "Handling forecast command with arguments: %s", arguments)
        if arguments is None or len(arguments) <= 0:
            self.mesh_service.send_reply("You must provide a location.", data)
            return
        query = ' '.join(arguments)
        coords: GpsLocation | None = self.geo_service.get_coords(query)
        if coords is None:
            self.mesh_service.send_reply(
                "Unable to identify the location for your query.", data)
            return
        zone = self.api_service.get_zone(coords.latitude, coords.longitude)
        if zone is None:
            self.mesh_service.send_reply(
                "Unable to identify the location for your query.", data)
            return
        forecasts: list[WeatherForecast] | None = self.api_service.get_forecasts(
            zone)
        if forecasts is None or len(forecasts) <= 0:
            self.mesh_service.send_reply(
                "Unable to lookup the conditions for that location.", data)
            return
        forecast_summary = ""
        for forecast in forecasts:
            fname = forecast.name
            desc = forecast.forecast
            if desc is None:
                continue
            if len(forecast_summary) == 0:
                if fname is not None:
                    forecast_summary = fname + ": " + desc
                else:
                    forecast_summary = desc
            elif len(forecast_summary) < 200:
                forecast_summary = forecast_summary + "\n" + fname + ": " + desc
        if len(forecast_summary) <= 0:
            self.mesh_service.send_reply(
                "Unable to lookup the forecast for that location.", data)
            return
        self.mesh_service.send_reply(forecast_summary, data)
