from dataclasses import dataclass


@dataclass
class GpsLocation:
    """
    Represents a GPS location with latitude and longitude.
    """
    __slots__ = ['latitude', 'longitude']
    latitude: float
    longitude: float
