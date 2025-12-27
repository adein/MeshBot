import requests
import logging
import yaml
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse
from pathlib import PurePosixPath

@dataclass
class WeatherAlert:
    __slots__ = ['alert_id', 'expires', 'severity', 'headline', 'description', 'event', 'areas']
    alert_id: str
    expires: datetime
    severity: str
    headline: str
    description: str
    event: str
    areas: str

@dataclass
class WeatherConditions:
    __slots__ = ['location', 'location_id', 'description', 'heat_index', 'humidity', 'precipitation', 'pressure', 'temperature', 'wind_chill', 'wind_speed']
    location: str
    location_id: str
    description: str
    heat_index: float
    humidity: float
    precipitation: float
    pressure: float
    temperature: float
    wind_chill: float
    wind_speed: float

@dataclass
class WeatherForecast:
    __slots__ = ['name', 'forecast']
    name: str
    forecast: str

class NwsWeatherService:
    """
    Service to fetch weather information from the NWS.
    """
    BASE_URL = "https://api.weather.gov"
    ALERTS_PATH =  "alerts/active/zone"
    FORECAST_PATH =  "forecast"
    LIMIT_PARAM = "limit"
    OBSERVATIONS_PATH = 'observations'
    ZONES_PATH =  "zones"
    POINTS_PATH =  "points"
    HEADERS = {
        "accept": "application/geo+json"
    }

    def __init__(self):
        self.logger = logging.getLogger("Service.NwsWeather")
        config_data = self._load_config()
        self.config = config_data.get('services', {}).get('nws_weather_service', {})
        self.FORECAST_ZONE_TYPE = self.config.get('forecast_zone_type', 'land')

    def _load_config(self):
        try:
            with open("config.yaml", "r") as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print("config.yaml not found. Exiting.")
            sys.exit(1)

    def get_zone(self, latitude, longitude):
        """
        Fetches the NWS Zone given lat/long.
        Returns a string of the zone ID, or None otherwise.
        """
        if latitude == None or longitude == None:
            return None
        url = f"{self.BASE_URL}/{self.POINTS_PATH}/{latitude},{longitude}"

        try:
            response = requests.get(url, headers=self.HEADERS, timeout=5)
            response.raise_for_status() # Raises HTTPError for 4xx/5xx responses
            
            data = response.json()
            if 'properties' not in data:
                self.logger.warn(f"Get zone missing 'properties'")
                return None
            properties = data['properties']
            if 'forecastZone' not in properties:
                self.logger.warn(f"Get zone missing 'forecastZone'")
                return None
            zone_url = properties['forecastZone']
            path = urlparse(zone_url).path
            if path == None:
                self.logger.warn(f"Get zone unable to process forecast zone url to get path")
                return None
            return PurePosixPath(path).name

        except requests.exceptions.Timeout:
            self.logger.error(f"Request timed out connecting to {url}")
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"HTTP Error: {e}")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"General Connection Error: {e}")
            
        return None

    def get_alerts(self, zone):
        """
        Fetches the active weather alerts.
        Returns a list of WeatherAlerts, or None otherwise.
        """
        url = f"{self.BASE_URL}/{self.ALERTS_PATH}/{zone}"
        
        try:
            response = requests.get(url, headers=self.HEADERS, timeout=5)
            response.raise_for_status() # Raises HTTPError for 4xx/5xx responses
            
            data = response.json()
            if 'features' not in data:
                return None
            alerts_features = data['features']
            if len(alerts_features) <= 0:
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
                if alert_id == None or expires == None or severity == None or headline == None:
                    continue
                expires_dt = datetime.fromisoformat(expires)
                timestamp_utc = expires_dt.astimezone(timezone.utc)
                now_utc = datetime.now(timezone.utc)
                if now_utc > timestamp_utc:
                    # Alert is expired
                    continue
                alert = WeatherAlert(alert_id, timestamp_utc, severity, headline, description, event, areas)
                alerts.append(alert)
            return alerts

        except requests.exceptions.Timeout:
            self.logger.error(f"Request timed out connecting to {url}")
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"HTTP Error: {e}")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"General Connection Error: {e}")
            
        return None

    def get_conditions(self, zone):
        """
        Fetches the weather conditions for a zoneId.
        Returns the current WeatherConditions, or None otherwise.
        """
        url = f"{self.BASE_URL}/{self.ZONES_PATH}/{self.FORECAST_PATH}/{zone}/{self.OBSERVATIONS_PATH}"
        
        try:
            params = {
                self.LIMIT_PARAM : 1
            }
            response = requests.get(url, params=params, headers=self.HEADERS, timeout=5)
            response.raise_for_status() # Raises HTTPError for 4xx/5xx responses
            
            data = response.json()
            if 'features' not in data:
                self.logger.warn(f"Get conditions missing 'features'")
                return None
            features = data['features']
            if features == None or len(features) <= 0:
                self.logger.warn(f"Get conditions features is empty")
                return None
            current = features[0]
            if 'properties' not in current:
                self.logger.warn(f"Get conditions missing 'properties'")
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
            if 'textDescription' in properties:
                description = properties['textDescription']
            if 'heatIndex' in properties and 'value' in properties['heatIndex']:
                heat_index = self._convert_temp(properties['heatIndex']['value'])
            if 'relativeHumidity' in properties and 'value' in properties['relativeHumidity']:
                humidity = properties['relativeHumidity']['value']
            if 'precipitationLast3Hours' in properties and 'value' in properties['precipitationLast3Hours']:
                precipitation = self._convert_mm(properties['precipitationLast3Hours']['value'])
            if 'barometricPressure' in properties and 'value' in properties['barometricPressure']:
                pressure = properties['barometricPressure']['value']
            if 'temperature' in properties and 'value' in properties['temperature']:
                temperature = self._convert_temp(properties['temperature']['value'])
            if 'windChill' in properties and 'value' in properties['windChill']:
                wind_chill = self._convert_temp(properties['windChill']['value'])
            if 'windSpeed' in properties and 'value' in properties['windSpeed']:
                wind_speed = self._convert_speed(properties['windSpeed']['value'])
            conditions = WeatherConditions(location, location_id, description, heat_index, humidity, precipitation, pressure, temperature, wind_chill, wind_speed)
            return conditions

        except requests.exceptions.Timeout:
            self.logger.error(f"Request timed out connecting to {url}")
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"HTTP Error: {e}")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"General Connection Error: {e}")
            
        return None

    def get_forecasts(self, zone):
        """
        Fetches the weather forecast for a zoneId.
        Returns a list of WeatherForecasts, or None otherwise.
        """
        url = f"{self.BASE_URL}/{self.ZONES_PATH}/{self.FORECAST_ZONE_TYPE}/{zone}/{self.FORECAST_PATH}"
        
        try:
            response = requests.get(url, headers=self.HEADERS, timeout=5)
            response.raise_for_status() # Raises HTTPError for 4xx/5xx responses
            
            data = response.json()
            if 'properties' not in data:
                return None
            properties = data['properties']
            if 'periods' not in properties:
                return None
            periods = properties['periods']
            if periods == None or len(periods) <= 0:
                return None
            forecasts=[]
            for current_period in periods:
                if 'name' not in current_period or 'detailedForecast' not in current_period:
                    continue
                forecast = WeatherForecast(current_period['name'], current_period['detailedForecast'])
                forecasts.append(forecast)
            return forecasts

        except requests.exceptions.Timeout:
            self.logger.error(f"Request timed out connecting to {url}")
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"HTTP Error: {e}")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"General Connection Error: {e}")
            
        return None

    def _convert_temp(self, temp_in_c):
        if temp_in_c == None:
            return None
        return (temp_in_c * 1.8) + 32

    def _convert_speed(self, speed_in_kmph):
        if speed_in_kmph == None:
            return None
        return speed_in_kmph * 0.621371

    def _convert_mm(self, amount_in_mm):
        if amount_in_mm == None:
            return None
        return amount_in_mm / 25.4

