# qr_app/priority.py
"""Tank Test Priority: transparent rules that decide which tanks need a repeat measurement, a scheduled
test or human review. Pure functions: no database or network access, so every rule is unit-tested.

Boundary conventions (documented and tested):
  chlorine below minimum   -> value <  CHLORINE_MIN_MG_L       (exactly the minimum is not "below")
  reading is fresh         -> age   <= *_MAX_AGE_HOURS          (exactly the limit is still fresh)
  warm tank water          -> temp  >= WATER_WARM_C
  hot forecast             -> forecast max air temp >= FORECAST_HOT_C

These rules prioritise *measurement and review*. They do not predict chlorine levels, do not establish
potability and never instruct anyone to chlorinate or isolate a tank.
"""
from dataclasses import dataclass, field
from datetime import timedelta

LEVELS = ('urgent', 'high', 'medium', 'low', 'none')
DUE_IN = {'urgent': timedelta(0), 'high': timedelta(days=1), 'medium': timedelta(days=3), 'low': timedelta(days=3)}
ACTIONS = {
    'review': 'Warden review',
    'repeat': 'Repeat measurement',
    'test': 'Scheduled test',
    'profile': 'Complete thermal profile',
}
ACTIONABLE = ('review', 'repeat', 'test')


@dataclass
class Reading:
    value: float
    measured_at: object
    method: str = ''


@dataclass
class Priority:
    level: str = 'none'
    action: str = ''
    reasons: list = field(default_factory=list)
    context: list = field(default_factory=list)

    @property
    def actionable(self):
        return self.action in ACTIONABLE

    @property
    def action_label(self):
        return ACTIONS.get(self.action, 'No action needed')

    @property
    def rank(self):
        return LEVELS.index(self.level)


def hours_old(reading, now):
    return (now - reading.measured_at).total_seconds() / 3600


def evaluate(tank, chlorine, water_temp, forecast, cfg, now, water_forecast=None):
    """tank: object with sun_exposed, placement, shade. chlorine / water_temp: latest Reading or None.
    forecast: weather.Forecast. cfg: settings.DHARA_PRIORITY.
    water_forecast: optional twin.TwinResult; used only if it passed held-out validation, and only for
    forecast hours inside the calibrated weather range."""
    p = Priority()
    cl_min, cl_max = cfg['CHLORINE_MIN_MG_L'], cfg['CHLORINE_MAX_MG_L']

    # --- Heat context (affects urgency only; never creates a "below threshold" finding on its own) ---
    hot_forecast = forecast.available and forecast.max_next_days is not None \
        and forecast.max_next_days >= cfg['FORECAST_HOT_C']
    temp_fresh = water_temp is not None and hours_old(water_temp, now) <= cfg['TEMP_MAX_AGE_HOURS']
    warm_water = temp_fresh and water_temp.value >= cfg['WATER_WARM_C']
    if not forecast.available:
        p.context.append(f'Weather forecast unavailable ({forecast.error}) — ranked without weather context.')
    elif hot_forecast:
        p.context.append(f'Forecast maximum air temperature {forecast.max_next_days:.1f} °C in the next days '
                         f'(≥ {cfg["FORECAST_HOT_C"]:g} °C). This is air, not tank water.')
    if warm_water:
        p.context.append(f'Latest tank water temperature {water_temp.value:.1f} °C (≥ {cfg["WATER_WARM_C"]:g} °C).')
    if tank.sun_exposed:
        p.context.append('Thermal profile: above ground in full sun.')
    warm_forecast = False
    if water_forecast is not None and water_forecast.ok and water_forecast.forecast_max_in_range:
        peak, when = water_forecast.forecast_max_in_range
        warm_forecast = peak >= cfg['WATER_WARM_C']
        if warm_forecast:
            p.context.append(f'Thermal twin forecasts tank water {peak:.1f} °C at {when:%a %H:%M} '
                             f'(validated error ±{water_forecast.holdout_mae:.1f} °C) — '
                             f'≥ {cfg["WATER_WARM_C"]:g} °C.')
    heat = hot_forecast or warm_water or warm_forecast

    def set_(level, action, reason):
        p.level, p.action = level, action
        p.reasons.append(reason)

    # --- Free chlorine rules, first match wins ---
    if chlorine is None:
        set_('high' if heat else 'medium', 'test', 'No free-chlorine reading on record for this tank.')
    else:
        age = hours_old(chlorine, now)
        fresh = age <= cfg['CHLORINE_MAX_AGE_HOURS']
        if not fresh:
            set_('high' if heat else 'medium', 'test',
                 f'Latest free-chlorine reading is {age:.0f} h old (limit {cfg["CHLORINE_MAX_AGE_HOURS"]:g} h).')
        elif chlorine.value < cl_min:
            set_('urgent', 'review',
                 f'Latest free chlorine {chlorine.value:.2f} mg/L is below the configured minimum {cl_min:g} mg/L. '
                 'A warden should review it and confirm with a repeat measurement.')
        elif chlorine.value > cl_max:
            set_('medium', 'review',
                 f'Latest free chlorine {chlorine.value:.2f} mg/L is above the configured maximum {cl_max:g} mg/L.')
        elif chlorine.value < round(cl_min + cfg['CHLORINE_NEAR_MARGIN_MG_L'], 6):  # avoid 0.2+0.1 float drift
            set_('high' if heat else 'medium', 'repeat',
                 f'Latest free chlorine {chlorine.value:.2f} mg/L is within '
                 f'{cfg["CHLORINE_NEAR_MARGIN_MG_L"]:g} mg/L of the configured minimum.')
        elif heat and age > cfg['WARM_RETEST_HOURS']:
            set_('medium', 'repeat',
                 f'Heat context and the latest chlorine reading is {age:.0f} h old '
                 f'(re-test after {cfg["WARM_RETEST_HOURS"]:g} h in heat).')

    # --- Temperature gap on a sun-exposed tank in a hot forecast ---
    if not p.action and tank.sun_exposed and hot_forecast and not temp_fresh:
        set_('low', 'test', 'Sun-exposed tank with a hot forecast and no recent water-temperature reading.')

    # --- Informational only (no follow-up) ---
    if not p.action and ('unknown' in (tank.placement, tank.shade)):
        set_('low', 'profile', 'Placement or sun exposure not recorded, so heat context cannot be assessed.')
    return p
