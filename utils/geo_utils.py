import logging
import reverse_geocoder as rg

from geopy.geocoders import Nominatim
from functools import lru_cache

geolocator = Nominatim(user_agent="meshbot_admin_console")
logger = logging.getLogger("Utils.Geo")

@lru_cache(maxsize=100) # Cache the last 100 lookups
def get_city_state_online(lat, lon):
    """
    Converts lat/lon to 'City, State'.
    Returns the string, or 'Unknown'/'N/A' on failure.
    """
    if not lat or not lon:
        return "N/A"

    logger.info(f"Reverse geocoding {lat},{lon}...")

    try:
        if float(lat) == 0.0 and float(lon) == 0.0:
            return "N/A"
        location = geolocator.reverse(f"{lat}, {lon}", language='en', exactly_one=True)
        if location:
            address = location.raw.get('address', {})
            city = address.get('city') or address.get('town') or address.get('village') or address.get('hamlet') or "Unknown"
            state = address.get('state') or ""
            if state:
                return f"{city}, {state}"
            return city
            
    except Exception as e:
        logger.warning(f"Geocoding failed for {lat},{lon}: {e}", exc_info=True)
    
    return "Unknown"
    
def get_city_state_offline(lat, lon):
    """
    Converts lat/lon to 'City, State' using offline lookup.
    Returns the string, or 'Unknown'/'N/A' on failure.
    """
    if not lat or not lon:
        return "N/A"

    logger.info(f"Reverse geocoding {lat},{lon}...")

    try:
        if float(lat) == 0.0 and float(lon) == 0.0:
            return "N/A"
        coordinates = (lat, lon)
        results = rg.search([coordinates], mode=1, verbose=False)
        if results:
            data = results[0]
            city = data.get('name', 'Unknown')
            state = data.get('admin1', '') # 'admin1' is usually the State/Province
            if state:
                return f"{city}, {state}"
            return city
        else:
            logger.info(f"No results from offline geocoding for {lat},{lon}")

    except Exception as e:
        logger.warning(f"Offline Geocoding failed: {e}", exc_info=True)
    
    return "Unknown"