# qr_app/weather.py
"""Open-Meteo forecast client. Returns *forecast air temperature* for the campus location. This is
weather context only and is never stored or shown as tank-water temperature."""
import json
import logging
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)
CACHE_SECONDS = 3600


@dataclass
class Forecast:
    available: bool
    daily_max_c: list = field(default_factory=list)   # [(date, max air °C), ...] in TIME_ZONE
    fetched_at: object = None
    error: str = ''
    source: str = 'Open-Meteo'

    @property
    def max_next_days(self):
        return max((t for _, t in self.daily_max_c), default=None)


def unavailable(reason):
    return Forecast(available=False, error=reason)


def parse(payload: dict) -> Forecast:
    try:
        days = payload['daily']['time']
        temps = payload['daily']['temperature_2m_max']
        if len(days) != len(temps) or not days:
            raise ValueError('mismatched or empty daily arrays')
        daily = [(date.fromisoformat(d), float(t)) for d, t in zip(days, temps) if t is not None]
        if not daily:
            raise ValueError('no temperature values')
    except (KeyError, TypeError, ValueError) as e:
        return unavailable(f'Unexpected forecast format ({e}).')
    return Forecast(available=True, daily_max_c=daily, fetched_at=timezone.now())


def fetch(latitude, longitude, days=3) -> Forecast:
    """Never raises: network, HTTP and format errors return Forecast(available=False)."""
    if latitude is None or longitude is None:
        return unavailable('Campus location is not set (Institution settings).')
    key = f'dhara-forecast:{float(latitude):.3f}:{float(longitude):.3f}:{days}:{settings.TIME_ZONE}'
    cached = cache.get(key)
    if cached is not None:
        return cached
    query = urllib.parse.urlencode({
        'latitude': f'{float(latitude):.4f}', 'longitude': f'{float(longitude):.4f}',
        'daily': 'temperature_2m_max', 'timezone': settings.TIME_ZONE, 'forecast_days': days,
    })
    try:
        with urllib.request.urlopen(f'{settings.OPEN_METEO_URL}?{query}', timeout=settings.OPEN_METEO_TIMEOUT) as r:
            result = parse(json.loads(r.read().decode('utf-8')))
    except (OSError, ValueError) as e:   # URLError, HTTPError, timeouts, bad JSON
        logger.warning('Open-Meteo forecast unavailable: %s', e)
        result = unavailable('Weather forecast service could not be reached.')
    cache.set(key, result, CACHE_SECONDS if result.available else 300)
    return result


@dataclass
class Hourly:
    available: bool
    rows: dict = field(default_factory=dict)   # {aware local hour start: (air °C, solar kW/m² over [h, h+1))}
    error: str = ''


def parse_hourly(payload: dict, tz) -> Hourly:
    """Open-Meteo shortwave_radiation at time h is the mean over the *preceding* hour, so the solar input
    for the interval starting at h is the value labelled h+1."""
    from datetime import datetime, timedelta
    try:
        times = payload['hourly']['time']
        air = payload['hourly']['temperature_2m']
        sw = payload['hourly']['shortwave_radiation']
        if not (len(times) == len(air) == len(sw)) or not times:
            raise ValueError('mismatched or empty hourly arrays')
        stamps = [datetime.fromisoformat(t).replace(tzinfo=tz) for t in times]
        sw_by = dict(zip(stamps, sw))
        rows = {}
        for h, a in zip(stamps, air):
            g = sw_by.get(h + timedelta(hours=1))
            if a is not None and g is not None:
                rows[h] = (float(a), float(g) / 1000.0)
        if not rows:
            raise ValueError('no usable hourly values')
    except (KeyError, TypeError, ValueError) as e:
        return Hourly(False, error=f'Unexpected hourly format ({e}).')
    return Hourly(True, rows)


def fetch_hourly(latitude, longitude, past_days=30, forecast_days=3) -> Hourly:
    """Recent past + forecast hourly air temperature and solar radiation. Never raises."""
    from zoneinfo import ZoneInfo
    if latitude is None or longitude is None:
        return Hourly(False, error='Campus location is not set (Institution settings).')
    key = f'dhara-hourly:{float(latitude):.3f}:{float(longitude):.3f}:{past_days}:{forecast_days}:{settings.TIME_ZONE}'
    cached = cache.get(key)
    if cached is not None:
        return cached
    query = urllib.parse.urlencode({
        'latitude': f'{float(latitude):.4f}', 'longitude': f'{float(longitude):.4f}',
        'hourly': 'temperature_2m,shortwave_radiation', 'timezone': settings.TIME_ZONE,
        'past_days': past_days, 'forecast_days': forecast_days,
    })
    try:
        with urllib.request.urlopen(f'{settings.OPEN_METEO_URL}?{query}', timeout=settings.OPEN_METEO_TIMEOUT) as r:
            result = parse_hourly(json.loads(r.read().decode('utf-8')), ZoneInfo(settings.TIME_ZONE))
    except (OSError, ValueError) as e:
        logger.warning('Open-Meteo hourly unavailable: %s', e)
        result = Hourly(False, error='Weather service could not be reached.')
    cache.set(key, result, 1800 if result.available else 300)
    return result
