import logging
from functools import lru_cache

import reverse_geocoder as rg
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
    if not lat or not lon:
        return "Unknown"

    logger.info("Reverse geocoding %s, %s...", lat, lon)

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

    except Exception as e:
        logger.warning("Geocoding failed for %s, %s: %s",
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
    if not lat or not lon:
        return "Unknown"

    logger.info("Reverse geocoding %s, %s...", lat, lon)

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
            logger.info(
                "No results from offline geocoding for %s, %s", lat, lon)

    except Exception as e:
        logger.warning("Geocoding failed for %s, %s: %s",
                       lat, lon, e, exc_info=True)

    return "Unknown"
