from dataclasses import dataclass
from datetime import datetime


@dataclass
class WeatherAlertData:
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
class WeatherConditionsData:
    """
    Data class to hold weather conditions information.
    """
    __slots__ = ['location', 'location_id', 'description',
                 'temperature', 'apparent_temperature', 'humidity',
                 'precipitation', 'pressure', 'wind_speed', 'wind_gusts']
    location: str | None
    location_id: str | None
    description: str | None
    temperature: float | None
    apparent_temperature: float | None
    humidity: float | None
    precipitation: float | None
    pressure: float | None
    wind_speed: float | None
    wind_gusts: float | None


@dataclass
class WeatherForecastData:
    """
    Data class to hold weather forecast information.
    """
    __slots__ = ['day_or_time_period', 'summary',
                 'low_temperature', 'high_temperature', 'humidity',
                 'precipitation_probability', 'precipitation_sum',
                 'wind_speed', 'wind_gusts', 'sunrise', 'sunset',
                 'sunshine_duration', 'uv_index_max']
    day_or_time_period: str
    summary: str | None
    low_temperature: float | None
    high_temperature: float | None
    humidity: float | None
    precipitation_probability: float | None
    precipitation_sum: float | None
    wind_speed: float | None
    wind_gusts: float | None
    sunrise: str | None
    sunset: str | None
    sunshine_duration: float | None
    uv_index_max: float | None
