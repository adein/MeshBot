import logging

import openmeteo_requests
import requests_cache
from retry_requests import retry

from dataclasses import dataclass
from datetime import datetime, timezone

from models.weather import WeatherConditionsData, WeatherForecastData


BASE_URL = "https://api.open-meteo.com/v1/forecast"

WEATHER_CODES = {
    0: "Clear sky ☀️",
    1: "Mainly clear 🌤", 2: "Partly cloudy ⛅", 3: "Overcast ☁️",
    45: "Fog 🌫", 48: "Depositing rime fog 🌫",
    51: "Light Drizzle 💧", 53: "Moderate Drizzle 💧", 55: "Dense Drizzle 💧",
    56: "Light Freezing Drizzle ❄️", 57: "Dense Freezing Drizzle ❄️",
    61: "Slight Rain ☔️", 63: "Moderate Rain ☔️", 65: "Heavy Rain ☔️",
    66: "Light Freezing Rain ❄️", 67: "Heavy Freezing Rain ❄️",
    71: "Slight Snow 🌨", 73: "Moderate Snow 🌨", 75: "Heavy Snow 🌨",
    77: "Snow grains 🌨",
    80: "Slight Rain Showers 🌦", 81: "Moderate Rain Showers 🌦", 82: "Violent Rain Showers ⛈",
    85: "Slight Snow Showers 🌨", 86: "Heavy Snow Showers 🌨",
    95: "Thunderstorm ⛈️", 96: "Thunderstorm with slight hail ⛈️", 99: "Thunderstorm with heavy hail ⛈️"
}


class OpenMeteoWeatherService:
    """
    Service to fetch weather data from OpenMeteo API.
    """

    def __init__(self):
        self.logger = logging.getLogger("Service.OpenMeteoWeather")
        # Setup Cache (expires after 1 hour)
        cache_session = requests_cache.CachedSession(
            '.cache_weather', expire_after=3600)
        # Setup Retry Logic
        retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
        # Initialize Client
        self.client = openmeteo_requests.Client(session=retry_session)
        self.logger.debug("Open-Meteo Service initialized (with caching).")

    def get_conditions(self, latitude: float, longitude: float) -> WeatherConditionsData | None:
        """
        Fetch current weather conditions for the given coordinates.

        :param latitude: The latitude of the location
        :type latitude: float
        :param longitude: The longitude of the location
        :type longitude: float
        :return: Current weather conditions data or None if fetching fails
        :rtype: WeatherConditionsData | None
        """

        requested_vars = [
            "weather_code",
            "temperature_2m",
            "apparent_temperature",
            "precipitation",
            "relative_humidity_2m",
            "surface_pressure",
            "wind_speed_10m",
            "wind_gusts_10m",
        ]
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": requested_vars,
            "wind_speed_unit": "mph",
            "temperature_unit": "fahrenheit",
            "precipitation_unit": "inch",
            "timezone": "auto"
        }
        try:
            responses = self.client.weather_api(BASE_URL, params=params)
            response = responses[0]
            current = response.Current()
            current_weather_code = current.Variables(0).Value()
            current_temperature_2m = current.Variables(1).Value()
            current_apparent_temperature = current.Variables(2).Value()
            current_precipitation = current.Variables(3).Value()
            current_relative_humidity_2m = current.Variables(4).Value()
            current_surface_pressure = current.Variables(5).Value()
            current_wind_speed_10m = current.Variables(6).Value()
            current_wind_gusts_10m = current.Variables(7).Value()
            description = WEATHER_CODES.get(current_weather_code)
            conditions = WeatherConditionsData(
                None,
                None,
                description,
                current_temperature_2m,
                current_apparent_temperature,
                current_relative_humidity_2m,
                current_precipitation,
                current_surface_pressure,
                current_wind_speed_10m,
                current_wind_gusts_10m
            )
            return conditions

        except Exception as e:
            self.logger.error("Failed to fetch current weather: %s", e)
        return None

    def get_forecasts(self, latitude: float, longitude: float, days: int = 1) -> list[WeatherForecastData] | None:
        """
        Fetches the weather forecast for the given coordinates and days.

        :param latitude: The latitude of the location
        :type latitude: float
        :param longitude: The longitude of the location
        :type longitude: float
        :param days: The number of days to forecast
        :type days: int
        :return: A list of weather forecast data or None if fetching fails
        :rtype: list[WeatherForecastData] | None
        """

        requested_vars = [
            "weather_code",
            "temperature_2m_max",
            "temperature_2m_min",
            "apparent_temperature_max",
            "apparent_temperature_min",
            "sunrise",
            "sunset",
            "daylight_duration",
            "sunshine_duration",
            "uv_index_max",
            "uv_index_clear_sky_max",
            "precipitation_sum",
            "precipitation_hours",
            "precipitation_probability_max",
            "wind_speed_10m_max",
            "wind_gusts_10m_max",
            "wind_direction_10m_dominant",
            "relative_humidity_2m_max"
        ]

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": requested_vars,
            "wind_speed_unit": "mph",
            "temperature_unit": "fahrenheit",
            "precipitation_unit": "inch",
            "timezone": "auto",
            "forecast_days": days
        }

        try:
            responses = self.client.weather_api(BASE_URL, params=params)
            response = responses[0]
            daily = response.Daily()

            # Map values to variable names using a helper dictionary
            daily_data = {}
            for i, var_name in enumerate(requested_vars):
                variable = daily.Variables(i)
                if variable:
                    val_array = variable.ValuesAsNumpy()
                    if hasattr(val_array, 'flatten'):
                        daily_data[var_name] = val_array.flatten().tolist()
                    else:
                        # Fallback if numpy isn't behaving as expected
                        daily_data[var_name] = [val_array]
                else:
                    # Fill with zeroes if missing to prevent index errors
                    daily_data[var_name] = [0] * days

            # Start and End times
            # OpenMeteo returns range(start, end, step)
            start = daily.Time()
            end = daily.TimeEnd()
            step = daily.Interval()

            forecasts: list[WeatherForecastData] = []
            for i, time_seconds in enumerate(range(start, end, step)):
                if i >= len(daily_data["weather_code"]):
                    break
                forecast_date = datetime.fromtimestamp(
                    time_seconds, timezone.utc)
                day_name: str = forecast_date.strftime('%A')

                wmo_code = int(self._get_val("weather_code", i, daily_data))
                summary = WEATHER_CODES.get(wmo_code, None)

                # Convert Unix timestamps to readable strings
                sunrise_ts = self._get_val("sunrise", i, daily_data)
                sunset_ts = self._get_val("sunset", i, daily_data)
                sunrise_str = datetime.fromtimestamp(
                    sunrise_ts, timezone.utc).strftime('%H:%M')
                sunset_str = datetime.fromtimestamp(
                    sunset_ts, timezone.utc).strftime('%H:%M')

                low_temperature = float(self._get_val(
                    "temperature_2m_min", i, daily_data))
                high_temperature = float(self._get_val(
                    "temperature_2m_max", i, daily_data))
                humidity = float(self._get_val(
                    "relative_humidity_2m_max", i, daily_data))
                precipitation_probability = int(
                    self._get_val("precipitation_probability_max", i, daily_data))
                precipitation_sum = float(self._get_val(
                    "precipitation_sum", i, daily_data))
                wind_speed = float(self._get_val(
                    "wind_speed_10m_max", i, daily_data))
                wind_gusts = float(self._get_val(
                    "wind_gusts_10m_max", i, daily_data))
                sunshine_duration = float(self._get_val(
                    "sunshine_duration", i, daily_data))
                uv_index_max = float(self._get_val(
                    "uv_index_max", i, daily_data))

                forecast = WeatherForecastData(
                    day_or_time_period=day_name,
                    summary=summary,
                    low_temperature=low_temperature,
                    high_temperature=high_temperature,
                    humidity=humidity,
                    precipitation_probability=precipitation_probability,
                    precipitation_sum=precipitation_sum,
                    wind_speed=wind_speed,
                    wind_gusts=wind_gusts,
                    sunrise=sunrise_str,
                    sunset=sunset_str,
                    sunshine_duration=sunshine_duration,
                    uv_index_max=uv_index_max,
                )
                forecasts.append(forecast)
            return forecasts

        except Exception as e:
            self.logger.error("Failed to fetch forecast: %s", e, exc_info=True)
            return None

    # Safe Access with defaults
    def _get_val(self, key, idx, data):
        try:
            return data.get(key, [])[idx]
        except IndexError:
            return 0
