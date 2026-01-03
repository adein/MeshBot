import logging
import requests
import yaml

from datetime import datetime, timezone
from urllib.parse import urlparse
from pathlib import PurePosixPath

from models.weather import WeatherAlert, WeatherConditions, WeatherForecast


BASE_URL = "https://api.weather.gov"
ALERTS_PATH = "alerts/active/zone"
FORECAST_PATH = "forecast"
LIMIT_PARAM = "limit"
OBSERVATIONS_PATH = 'observations'
ZONES_PATH = "zones"
POINTS_PATH = "points"
HEADERS = {
    "accept": "application/geo+json"
}


class NwsWeatherService:
    """
    Service to fetch weather information from the NWS.
    """

    def __init__(self):
        self.logger = logging.getLogger("Service.NwsWeather")
        try:
            with open("config.yaml", "r") as f:
                config_data = yaml.safe_load(f)
        except FileNotFoundError:
            self.logger.error("config.yaml not found!")
            return
        self.config = config_data.get(
            'services', {}).get('nws_weather_service', {})
        self.forecast_zone_type: str = self.config.get(
            'forecast_zone_type', 'land')

    def get_zone(self, latitude: float, longitude: float) -> str | None:
        """
        Fetches the NWS Zone given lat/long.

        :param latitude: The latitude of the location
        :type latitude: float
        :param longitude: The longitude of the location
        :type longitude: float
        :return: The NWS zone ID or None if not found
        :rtype: str | None
        """
        self.logger.debug("Get zone with: %f, %f", latitude, longitude)
        if latitude is None or longitude is None:
            return None
        url = f"{BASE_URL}/{POINTS_PATH}/{latitude},{longitude}"

        try:
            response = requests.get(url, headers=HEADERS, timeout=5)
            response.raise_for_status()  # Raises HTTPError for 4xx/5xx responses

            data = response.json()
            if 'properties' not in data:
                self.logger.warning("Get zone missing 'properties'")
                return None
            properties = data['properties']
            if 'forecastZone' not in properties:
                self.logger.warning("Get zone missing 'forecastZone'")
                return None
            zone_url = properties['forecastZone']
            path = urlparse(zone_url).path
            if path is None:
                self.logger.warning(
                    "Get zone unable to process forecast zone url to get path")
                return None
            return PurePosixPath(path).name

        except requests.exceptions.Timeout:
            self.logger.error("Request timed out connecting to %s", url)
        except requests.exceptions.HTTPError as e:
            self.logger.error("HTTP Error: %s", e)
        except requests.exceptions.RequestException as e:
            self.logger.error("General Connection Error: %s", e)

        return None

    def get_alerts(self, zone: str) -> list[WeatherAlert] | None:
        """
        Fetches the active weather alerts.

        :param zone: The NWS zone ID
        :type zone: str
        :return: A list of active WeatherAlert objects or None if no alerts are found
        :rtype: list[WeatherAlert] | None
        """
        self.logger.debug("Get alerts for zone: %s", zone)
        url = f"{BASE_URL}/{ALERTS_PATH}/{zone}"

        try:
            response = requests.get(url, headers=HEADERS, timeout=5)
            response.raise_for_status()  # Raises HTTPError for 4xx/5xx responses

            data = response.json()
            if 'features' not in data:
                self.logger.warning("Get alerts missing 'features'")
                return None
            alerts_features = data['features']
            if len(alerts_features) <= 0:
                self.logger.warning("Get alerts features is empty")
                return None
            # At least one alert
            alerts = []
            for current_alert in alerts_features:
                alert_id = current_alert['id']
                properties = current_alert['properties']
                areas = properties['areaDesc']
                expires = properties['expires']
                severity = properties['severity']
                description = properties['description']
                event = properties['event']
                parameters = properties['parameters']
                headline = parameters['NWSheadline'][0].capitalize()
                if alert_id is None or expires is None or severity is None or headline is None:
                    self.logger.debug("Alert is missing required fields")
                    continue
                expires_dt = datetime.fromisoformat(expires)
                timestamp_utc = expires_dt.astimezone(timezone.utc)
                now_utc = datetime.now(timezone.utc)
                if now_utc > timestamp_utc:
                    # Alert is expired
                    self.logger.debug("Alert is expired")
                    continue
                alert = WeatherAlert(
                    alert_id, timestamp_utc, severity, headline, description, event, areas)
                alerts.append(alert)
            return alerts

        except requests.exceptions.Timeout:
            self.logger.error("Request timed out connecting to %s", url)
        except requests.exceptions.HTTPError as e:
            self.logger.error("HTTP Error: %s", e)
        except requests.exceptions.RequestException as e:
            self.logger.error("General Connection Error: %s", e)
        return None

    def get_conditions(self, zone: str) -> WeatherConditions | None:
        """
        Fetches the weather conditions for a zoneId.

        :param zone: The NWS zone ID
        :type zone: str
        :return: The current WeatherConditions or None if not available
        :rtype: WeatherConditions | None
        """
        self.logger.debug("Get conditions for zone: %s", zone)
        url = f"{BASE_URL}/{ZONES_PATH}/{FORECAST_PATH}/{zone}/{OBSERVATIONS_PATH}"

        try:
            params = {
                LIMIT_PARAM: 1
            }
            response = requests.get(
                url, params=params, headers=HEADERS, timeout=5)
            response.raise_for_status()  # Raises HTTPError for 4xx/5xx responses

            data = response.json()
            if 'features' not in data:
                self.logger.warning("Get conditions missing 'features'")
                return None
            features = data['features']
            if features is None or len(features) <= 0:
                self.logger.warning("Get conditions features is empty")
                return None
            current = features[0]
            if 'properties' not in current:
                self.logger.warning("Get conditions missing 'properties'")
                return None
            properties = current['properties']

            location = None
            location_id = None
            description = None
            heat_index = None
            humidity = None
            precipitation = None
            pressure = None
            temperature = None
            wind_chill = None
            wind_speed = None

            if 'stationName' in properties:
                location = properties['stationName']
            if 'stationId' in properties:
                location_id = properties['stationId']
            if location is None or location_id is None:
                return None
            if 'textDescription' in properties:
                description = properties['textDescription']
            if 'heatIndex' in properties and 'value' in properties['heatIndex']:
                heat_index = self._convert_temp(
                    properties['heatIndex']['value'])
            if 'relativeHumidity' in properties and 'value' in properties['relativeHumidity']:
                humidity = properties['relativeHumidity']['value']
            if 'precipitationLast3Hours' in properties and 'value' in properties['precipitationLast3Hours']:
                precipitation = self._convert_mm(
                    properties['precipitationLast3Hours']['value'])
            if 'barometricPressure' in properties and 'value' in properties['barometricPressure']:
                pressure = properties['barometricPressure']['value']
            if 'temperature' in properties and 'value' in properties['temperature']:
                temperature = self._convert_temp(
                    properties['temperature']['value'])
            if 'windChill' in properties and 'value' in properties['windChill']:
                wind_chill = self._convert_temp(
                    properties['windChill']['value'])
            if 'windSpeed' in properties and 'value' in properties['windSpeed']:
                wind_speed = self._convert_speed(
                    properties['windSpeed']['value'])
            conditions = WeatherConditions(location, location_id, description, heat_index,
                                           humidity, precipitation, pressure, temperature, wind_chill, wind_speed)
            return conditions

        except requests.exceptions.Timeout:
            self.logger.error("Request timed out connecting to %s", url)
        except requests.exceptions.HTTPError as e:
            self.logger.error("HTTP Error: %s", e)
        except requests.exceptions.RequestException as e:
            self.logger.error("General Connection Error: %s", e)
        return None

    def get_forecasts(self, zone: str) -> list[WeatherForecast] | None:
        """
        Fetches the weather forecast for a zoneId.

        :param zone: The NWS zone ID
        :type zone: str
        :return: A list of WeatherForecast objects or None if not available
        :rtype: list[WeatherForecast] | None
        """
        self.logger.debug("Get forecasts for zone: %s", zone)
        url = f"{BASE_URL}/{ZONES_PATH}/{self.forecast_zone_type}/{zone}/{FORECAST_PATH}"

        try:
            response = requests.get(url, headers=HEADERS, timeout=5)
            response.raise_for_status()  # Raises HTTPError for 4xx/5xx responses

            data = response.json()
            if 'properties' not in data:
                self.logger.warning("Get forecasts missing 'properties'")
                return None
            properties = data['properties']
            if 'periods' not in properties:
                self.logger.warning("Get forecasts missing 'periods'")
                return None
            periods = properties['periods']
            if periods is None or len(periods) <= 0:
                self.logger.warning("Get forecasts periods is empty")
                return None
            forecasts = []
            for current_period in periods:
                if 'name' not in current_period or 'detailedForecast' not in current_period:
                    self.logger.debug(
                        "Get forecasts period is missing required fields")
                    continue
                forecast = WeatherForecast(
                    current_period['name'], current_period['detailedForecast'])
                forecasts.append(forecast)
            return forecasts

        except requests.exceptions.Timeout:
            self.logger.error("Request timed out connecting to %s", url)
        except requests.exceptions.HTTPError as e:
            self.logger.error("HTTP Error: %s", e)
        except requests.exceptions.RequestException as e:
            self.logger.error("General Connection Error: %s", e)
        return None

    def _convert_temp(self, temp_in_c: float | None) -> float | None:
        if temp_in_c is None:
            return None
        return (temp_in_c * 1.8) + 32

    def _convert_speed(self, speed_in_kmph: float | None) -> float | None:
        if speed_in_kmph is None:
            return None
        return speed_in_kmph * 0.621371

    def _convert_mm(self, amount_in_mm: float | None) -> float | None:
        if amount_in_mm is None:
            return None
        return amount_in_mm / 25.4
