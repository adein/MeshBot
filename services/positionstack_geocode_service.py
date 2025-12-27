import logging
import requests
import yaml
from dataclasses import dataclass

@dataclass
class GpsLocation:
    __slots__ = ['latitude', 'longitude']
    latitude: float
    longitude: float

class PositionstackGeocodeService:
    """
    Service to fetch geocoding information from the Positionstack API.
    """
    BASE_URL = "http://api.positionstack.com/v1/forward"
    API_KEY_PARAM = "access_key"
    COUNTRY_PARAM = "country"
    QUERY_PARAM = "query"

    def __init__(self):
        self.logger = logging.getLogger("Service.Positionstack")
        config_data = self._load_config()
        self.config = config_data.get('services', {}).get('positionstack_geocode_service', {})
        self.API_KEY = self.config.get('api_key', "INVALID")
        self.COUNTRY_LIMIT = self.config.get('country_limit', "US")

    def _load_config(self):
        try:
            with open("config.yaml", "r") as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print("config.yaml not found. Exiting.")
            sys.exit(1)

    def get_coords(self, query):
        """
        Fetches the latitude and longitude given a query (string).
        Returns GpsLocation of the query, or None otherwise.
        """
        url = f"{self.BASE_URL}"

        params = {
           self.API_KEY_PARAM : str(self.API_KEY),
           self.QUERY_PARAM : str(query),
           self.COUNTRY_PARAM : str(self.COUNTRY_LIMIT)
        }

        try:
            self.logger.info(f"Geo query with: {query}")
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status() # Raises HTTPError for 4xx/5xx responses
            response_json = response.json()
            #self.logger.info(f"Geo query response: {response_json}")
            if 'data' not in response_json:
                self.logger.warn(f"Geo response missing 'data'")
                return None
            data = response_json['data']
            if data == None or len(data) <= 0:
                self.logger.warn(f"Geo response 'data' is empty")
                return None
            first_data = data[0]
            if 'latitude' not in first_data or 'longitude' not in first_data:
                self.logger.warn(f"Geo response missing latitude or longitude")
                return None
            return GpsLocation(first_data['latitude'], first_data['longitude'])

        except requests.exceptions.Timeout:
            self.logger.error(f"Request timed out connecting to {url}")
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"HTTP Error: {e}")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"General Connection Error: {e}")
            
        return None

