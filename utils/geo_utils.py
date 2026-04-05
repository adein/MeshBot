import logging
from functools import lru_cache

import reverse_geocoder as rg
from geopy.distance import geodesic
from geopy.geocoders import Nominatim


geolocator = Nominatim(user_agent="meshbot_admin_console")
logger = logging.getLogger("Utils.Geo")


@lru_cache(maxsize=100)  # Cache the last 100 lookups
def get_city_state_online(lat: float, lon: float) -> str:
    """
    Converts lat/lon to 'City, State'.

    :param lat: The latitude of the location.
    :type lat: float
    :param lon: The longitude of the location.
    :type lon: float
    :return: The city and state as a string, or 'Unknown' on failure.
    :rtype: str
    """
    logger.debug("Reverse geocoding %s, %s...", lat, lon)
    if not lat or not lon:
        return "Unknown"
    try:
        location = geolocator.reverse(
            f"{lat}, {lon}", language='en', exactly_one=True)
        if location:
            address = location.raw.get('address', {})
            city = address.get('city') or address.get('town') or address.get(
                'village') or address.get('hamlet') or "Unknown"
            state = address.get('state') or ""
            if state:
                return f"{city}, {state}"
            return city
        else:
            logger.debug(
                "No results from online geocoding for %s, %s", lat, lon)

    except Exception as e:
        logger.error("Geocoding failed for %s, %s: %s",
                     lat, lon, e, exc_info=True)

    return "Unknown"


def get_city_state_offline(lat: float, lon: float) -> str:
    """
    Converts lat/lon to 'City, State' using offline lookup.

    :param lat: The latitude of the location.
    :type lat: float
    :param lon: The longitude of the location.
    :type lon: float
    :return: The city and state as a string, or 'Unknown' on failure.
    :rtype: str
    """
    logger.debug("Reverse geocoding %s, %s...", lat, lon)
    if not lat or not lon:
        return "Unknown"
    try:
        coordinates = (lat, lon)
        results = rg.search([coordinates], mode=1, verbose=False)
        if results:
            data = results[0]
            city = data.get('name', 'Unknown')
            # 'admin1' is usually the State/Province
            state = data.get('admin1', '')
            if state:
                return f"{city}, {state}"
            return city
        else:
            logger.debug(
                "No results from offline geocoding for %s, %s", lat, lon)

    except Exception as e:
        logger.error("Geocoding failed for %s, %s: %s",
                     lat, lon, e, exc_info=True)

    return "Unknown"


def get_lat_lon_from_string(location_query: str) -> tuple | None:
    """
    Converts 'City, State' to (lat, long).

    :param location_query: The location query string.
    :type location_query: str
    :return: The (lat, lon) tuple or None on failure.
    :rtype: tuple[float, float] | None
    """
    try:
        location = geolocator.geocode(location_query, timeout=5)
        if location:
            return (location.latitude, location.longitude)
    except Exception as e:
        logger.warning("Forward geocoding failed for '%s': %s",
                       location_query, e)
    return None


def calculate_distance(origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float) -> float | None:
    """
    Returns distance in Miles between two points.

    :param origin_lat: The latitude of the origin point.
    :type origin_lat: float
    :param origin_lon: The longitude of the origin point.
    :type origin_lon: float
    :param dest_lat: The latitude of the destination point.
    :type dest_lat: float
    :param dest_lon: The longitude of the destination point.
    :type dest_lon: float
    :return: The distance in miles, or 99999.0 on failure.
    :rtype: float
    """
    try:
        if not origin_lat or not dest_lat:
            return None
        return geodesic((origin_lat, origin_lon), (dest_lat, dest_lon)).miles
    except:
        return None
