from interfaces.bot_module import BotModule
from models.command import CommandData
from models.location import GpsLocation
from models.weather import WeatherForecastData
from services.openmeteo_weather_service import OpenMeteoWeatherService
from services.positionstack_geocode_service import PositionstackGeocodeService
from utils.geo_utils import get_city_state_offline
from utils.time_utils import duration_to_str


class WeatherForecast(BotModule):
    """
    Module to respond to 'forecast' commands with NWS weather forecast information.
    """

    def __init__(self, name, config, root_config, global_services, my_node=None):
        super().__init__(name, config, root_config, global_services, my_node)
        # Initialize the geocode service
        self.geo_service = PositionstackGeocodeService()
        # Initialize the weather service
        self.api_service = OpenMeteoWeatherService()
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
        forecasts: list[WeatherForecastData] | None = self.api_service.get_forecasts(
            coords.latitude, coords.longitude, days=2)
        if forecasts is None or len(forecasts) <= 0:
            self.mesh_service.send_reply(
                "Unable to lookup the conditions for that location.", data)
            return
        # location: str | None = get_city_state_offline(
        #    coords.latitude, coords.longitude)
        forecast_summary = ""
        separater = ""
        # if location is not None:
        #    forecast_summary = location + ":\n"
        for forecast in forecasts:
            sunshine_duration = duration_to_str(int(
                forecast.sunshine_duration)) if forecast.sunshine_duration is not None else None
            forecast_summary = forecast_summary + forecast.day_or_time_period + ": "
            if forecast.summary is not None:
                forecast_summary = forecast_summary + forecast.summary + "."
                separater = " "

            if forecast.high_temperature is not None or forecast.low_temperature is not None:
                forecast_summary = forecast_summary + separater + "🌡️ "
                if forecast.high_temperature is not None:
                    forecast_summary = forecast_summary + separater + \
                        "H: " + \
                        self._convert_num(forecast.high_temperature, 0) + "°"
                    separater = ", "
                if forecast.low_temperature is not None:
                    forecast_summary = forecast_summary + separater + \
                        "L: " + \
                        self._convert_num(forecast.low_temperature, 0) + "°"

            separater = ". "
            if forecast.humidity is not None:
                forecast_summary = forecast_summary + separater + \
                    "💧 " + \
                    self._convert_num(forecast.humidity, 0) + "%"
                separater = ", "
            if forecast.precipitation_probability is not None:
                forecast_summary = forecast_summary + separater + \
                    "🌧️ " + \
                    self._convert_num(
                        forecast.precipitation_probability, 0) + "%"
                separater = ", "
            if forecast.wind_speed is not None:
                forecast_summary = forecast_summary + separater + \
                    "💨 " + \
                    self._convert_num(forecast.wind_speed, 0) + "m/h"
                separater = ", "
            if sunshine_duration is not None:
                forecast_summary = forecast_summary + separater + \
                    "☀️ " + sunshine_duration
                separater = ","
            forecast_summary = forecast_summary + "\n"
        self.mesh_service.send_reply(forecast_summary, data)

    def _convert_num(self, number, digits: int = 1) -> str:
        return f"{number:.{digits}f}"
