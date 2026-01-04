from dataclasses import dataclass
from datetime import datetime


@dataclass
class WeatherAlert:
    """
    Data class to hold weather alert information.
    """
    __slots__ = ['alert_id', 'expires', 'severity',
                 'headline', 'description', 'event', 'areas']
    alert_id: str
    expires: datetime
    severity: str
    headline: str
    description: str | None
    event: str | None
    areas: str | None


@dataclass
class WeatherConditions:
    """
    Data class to hold weather conditions information.
    """
    __slots__ = ['location', 'location_id', 'description', 'heat_index', 'humidity',
                 'precipitation', 'pressure', 'temperature', 'wind_chill', 'wind_speed']
    location: str
    location_id: str
    description: str | None
    heat_index: float | None
    humidity: float | None
    precipitation: float | None
    pressure: float | None
    temperature: float | None
    wind_chill: float | None
    wind_speed: float | None


@dataclass
class WeatherForecast:
    """
    Data class to hold weather forecast information.
    """
    __slots__ = ['name', 'forecast']
    name: str
    forecast: str
