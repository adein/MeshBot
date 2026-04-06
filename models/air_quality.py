from dataclasses import dataclass


@dataclass
class AirQualityCityData:
    """
    Data class to hold air quality city information.
    """
    __slots__ = ['name', 'url']
    name: str | None
    url: str | None


@dataclass
class AirQualityCurrentMeasurementData:
    """
    Data class to hold current air quality measurement information.
    """
    __slots__ = ['co', 'dew', 'h', 'no2', 'o3',
                 'p', 'pm10', 'pm25', 'so2', 't', 'w', 'wg']
    dew: int | None
    h: int | None
    no2: float | None
    o3: float | None
    p: float | None
    pm10: int | None
    pm25: int | None
    so2: int | None
    t: float | None
    w: float | None
    wg: float | None


@dataclass
class AirQualityTimeData:
    """
    Data class to hold air quality time information.
    """
    __slots__ = ['s', 'tz', 'v', 'iso']
    s: str | None
    tz: str | None
    v: int | None
    iso: str | None


@dataclass
class AirQualityForecastItemData:
    """
    Data class to hold air quality forecast item information.
    """
    __slots__ = ['avg', 'day', 'max', 'min']
    avg: int | None
    day: str | None
    max: int | None
    min: int | None


@dataclass
class AirQualityDailyForecastData:
    """
    Data class to hold air quality daily forecast information.
    """
    __slots__ = ['pm10', 'pm25', 'uvi']
    pm10: list[AirQualityForecastItemData] | None
    pm25: list[AirQualityForecastItemData] | None
    uvi: list[AirQualityForecastItemData] | None


@dataclass
class AirQualityForecastData:
    """
    Data class to hold air quality forecast information.
    """
    __slots__ = ['daily']
    daily: AirQualityDailyForecastData | None


@dataclass
class AirQualityData:
    """
    Data class to hold air quality information.
    """
    __slots__ = ['aqi', 'city', 'dominentpol', 'iaqi', 'time', 'forecast']
    aqi: int | None
    city: AirQualityCityData | None
    dominentpol: str | None
    iaqi: AirQualityCurrentMeasurementData | None
    time: AirQualityTimeData | None
    forecast: AirQualityForecastData | None
