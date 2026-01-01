import logging
import requests
import yaml

from dataclasses import dataclass


BASE_URL = "http://api.positionstack.com/v1/forward"
API_KEY_PARAM = "access_key"
COUNTRY_PARAM = "country"
QUERY_PARAM = "query"


@dataclass
class GpsLocation:
    """
    Represents a GPS location with latitude and longitude.
    """
    __slots__ = ['latitude', 'longitude']
    latitude: float
    longitude: float


class PositionstackGeocodeService:
    """
    Service to fetch geocoding information from the Positionstack API.
    """

    def __init__(self):
        self.logger = logging.getLogger("Service.Positionstack")
        try:
            with open("config.yaml", "r") as f:
                config_data = yaml.safe_load(f)
        except FileNotFoundError:
            self.logger.error("config.yaml not found.")
            return
        self.config = config_data.get('services', {}).get(
            'positionstack_geocode_service', {})
        self.api_key: str = self.config.get('api_key', "INVALID")
        self.country_limit: str = self.config.get('country_limit', "US")

    def get_coords(self, query: str) -> GpsLocation | None:
        """
        Fetches the latitude and longitude given a query (string).

        :param query: The location query string.
        :type query: str
        :return: GpsLocation of the query, or None otherwise.
        :rtype: GpsLocation | None
        """
        self.logger.debug("Getting coordinates for query: %s", query)
        url = f"{BASE_URL}"
        params = {
            API_KEY_PARAM: str(self.api_key),
            QUERY_PARAM: str(query),
            COUNTRY_PARAM: str(self.country_limit)
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()  # Raises HTTPError for 4xx/5xx responses
            response_json = response.json()
            # self.logger.info(f"Geo query response: {response_json}")
            if 'data' not in response_json:
                self.logger.warning("Geo response missing 'data'")
                return None
            data = response_json['data']
            if data is None or len(data) <= 0:
                self.logger.warning("Geo response 'data' is empty")
                return None
            first_data = data[0]
            if 'latitude' not in first_data or 'longitude' not in first_data:
                self.logger.warning(
                    "Geo response missing latitude or longitude")
                return None
            return GpsLocation(first_data['latitude'], first_data['longitude'])

        except requests.exceptions.Timeout:
            self.logger.error("Request timed out connecting to %s", url)
        except requests.exceptions.HTTPError as e:
            self.logger.error("HTTP Error: %s", e)
        except requests.exceptions.RequestException as e:
            self.logger.error("General Connection Error: %s", e)

        return None
