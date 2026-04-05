import logging
import requests
import yaml

from datetime import datetime, timezone
from urllib.parse import urlparse

from models.air_quality import AirQualityData, AirQualityCityData, AirQualityCurrentMeasurementData, AirQualityTimeData, AirQualityForecastData, AirQualityDailyForecastData, AirQualityForecastItemData


BASE_URL = "https://api.waqi.info"
LAT_LNG_PATH = "feed/geo:"


class AirQualityService:
    """
    Service to fetch air quality information from AQICN.
    """

    def __init__(self):
        self.logger = logging.getLogger("Service.AirQuality")
        try:
            with open("config.yaml", "r") as f:
                config_data = yaml.safe_load(f)
        except FileNotFoundError:
            self.logger.error("config.yaml not found!")
            return
        self.config = config_data.get(
            'services', {}).get('aqicn_service', {})
        self.api_key: str = self.config.get('api_key', '')

    def get_air_quality(self, latitude: float, longitude: float) -> AirQualityData | None:
        """
        Fetches the air quality for a given latitude and longitude.

        :param latitude: The latitude of the location
        :type latitude: float
        :param longitude: The longitude of the location
        :type longitude: float
        :return: The current AirQualityData or None if not available
        :rtype: AirQualityData | None
        """
        self.logger.debug(
            "Get air quality for latitude: %s, longitude: %s", latitude, longitude)
        url = f"{BASE_URL}/{LAT_LNG_PATH}@{latitude};{longitude}"

        try:
            params = {
                "token": self.api_key
            }
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()  # Raises HTTPError for 4xx/5xx responses

            response_data = response.json()

            if 'data' not in response_data:
                self.logger.warning("Get air quality missing 'data'")
                return None
            data = response_data['data']
            if data is None:
                self.logger.warning("Get air quality data is empty")
                return None
            aqi = None
            city = None
            dominentpol = None
            iaqi = None
            time = None
            forecast = None
            if 'aqi' in data:
                aqi = data['aqi']
            if 'city' in data:
                city_data = data['city']
                city = AirQualityCityData(
                    name=city_data.get('name'),
                    url=city_data.get('url')
                )
            if 'dominentpol' in data:
                dominentpol = data['dominentpol']
            if 'iaqi' in data:
                iaqi_data = data['iaqi']
                iaqi = AirQualityCurrentMeasurementData(
                    dew=iaqi_data.get('dew', {}).get('v'),
                    h=iaqi_data.get('h', {}).get('v'),
                    no2=iaqi_data.get('no2', {}).get('v'),
                    o3=iaqi_data.get('o3', {}).get('v'),
                    p=iaqi_data.get('p', {}).get('v'),
                    pm10=iaqi_data.get('pm10', {}).get('v'),
                    pm25=iaqi_data.get('pm25', {}).get('v'),
                    so2=iaqi_data.get('so2', {}).get('v'),
                    t=iaqi_data.get('t', {}).get('v'),
                    w=iaqi_data.get('w', {}).get('v'),
                    wg=iaqi_data.get('wg', {}).get('v')
                )
            if 'time' in data:
                time_data = data['time']
                time = AirQualityTimeData(
                    s=time_data.get('s'),
                    tz=time_data.get('tz'),
                    v=time_data.get('v'),
                    iso=time_data.get('iso')
                )
            if 'forecast' in data and 'daily' in data['forecast']:
                daily_forecast_data = data['forecast']['daily']
                daily_forecast = AirQualityDailyForecastData(
                    pm10=[
                        AirQualityForecastItemData(
                            day=item.get('day'),
                            min=item.get('min'),
                            max=item.get('max'),
                            avg=item.get('avg')
                        ) for item in daily_forecast_data.get('pm10', [])
                    ],
                    pm25=[
                        AirQualityForecastItemData(
                            day=item.get('day'),
                            min=item.get('min'),
                            max=item.get('max'),
                            avg=item.get('avg')
                        ) for item in daily_forecast_data.get('pm25', [])
                    ],
                    uvi=[
                        AirQualityForecastItemData(
                            day=item.get('day'),
                            min=item.get('min'),
                            max=item.get('max'),
                            avg=item.get('avg')
                        ) for item in daily_forecast_data.get('uvi', [])
                    ]
                )
                forecast = AirQualityForecastData(daily=daily_forecast)
            return AirQualityData(
                aqi=aqi,
                city=city,
                dominentpol=dominentpol,
                iaqi=iaqi,
                time=time,
                forecast=forecast
            )
        except requests.exceptions.Timeout:
            self.logger.error("Request timed out connecting to %s", url)
        except requests.exceptions.HTTPError as e:
            self.logger.error("HTTP Error: %s", e)
        except requests.exceptions.RequestException as e:
            self.logger.error("General Connection Error: %s", e)
        return None
