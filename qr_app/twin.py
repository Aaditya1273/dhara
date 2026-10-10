# qr_app/twin.py
"""Thermal twin of a water tank: a lumped heat balance fitted to measured tank-water temperature.

Model (hourly, discretised):  T[k+1] - T[k] = a * G[k] + b * (Tair[k] - T[k]) + c
  G     global horizontal solar radiation (kW/m², Open-Meteo shortwave_radiation)
  Tair  air temperature (°C, Open-Meteo temperature_2m)
  a     solar gain per hour, b exchange with air per hour, c everything else (inflow, draw-off) on average
The equation is linear in (a, b, c), so it is fitted by ordinary least squares. Pure Python, no ML.

Honesty rules enforced here:
  * Validation is chronological: the model is fitted on the first 75% of hourly steps and scored by
    *free-running* simulation over the last 25% it never saw. Only that score is reported.
  * The model is used only if the parameters are physically plausible (a >= 0, 0 < b < 1) and the
    held-out mean absolute error is within the configured limit.
  * Forecasts never run longer than the held-out period they were validated on, and every hour whose
    weather lies outside the calibration range is flagged as extrapolated.
  * The uncertainty band is approximate: ±1.96 × held-out RMSE, assuming errors like those seen in validation.
"""
import math
from dataclasses import dataclass, field
from datetime import timedelta

T_975 = {1: 12.71, 2: 4.30, 3: 3.18, 4: 2.78, 5: 2.57, 6: 2.45, 7: 2.36, 8: 2.31, 9: 2.26, 10: 2.23,
         12: 2.18, 15: 2.13, 20: 2.09, 25: 2.06, 30: 2.04}


def t_crit(df):
    """Two-sided 95% Student-t critical value (table, conservative between entries)."""
    for d in sorted(T_975):
        if df <= d:
            return T_975[d]
    return 1.96


@dataclass
class TwinConfig:
    min_train_steps: int = 48
    min_holdout_steps: int = 24
    max_holdout_mae_c: float = 1.5
    max_start_age_hours: float = 3


@dataclass
class TwinResult:
    status: str                       # ok | insufficient | implausible | failed_validation | stale
    message: str
    params: tuple = None              # (a, b, c)
    n_train: int = 0
    n_holdout: int = 0
    holdout_mae: float = None
    holdout_rmse: float = None
    validated_horizon_h: int = 0
    air_range: tuple = None
    ghi_range: tuple = None
    forecast: list = field(default_factory=list)   # [(dt, temp, low, high, extrapolated)]

    @property
    def ok(self):
        return self.status == 'ok'

    @property
    def any_extrapolated(self):
        return any(f[4] for f in self.forecast)

    @property
    def forecast_max_in_range(self):
        temps = [(t, dt) for dt, t, _, _, ext in self.forecast if not ext]
        return max(temps) if temps else None


def hour_floor(dt, tz):
    return dt.astimezone(tz).replace(minute=0, second=0, microsecond=0)


def hourly_means(readings, tz):
    """readings: [(aware dt, °C)] -> {local hour start: mean °C}."""
    buckets = {}
    for dt, v in readings:
        buckets.setdefault(hour_floor(dt, tz), []).append(float(v))
    return {h: sum(vs) / len(vs) for h, vs in buckets.items()}


def build_steps(temps, weather):
    """temps: {hour: T}; weather: {hour: (Tair, G_kW)} -> chronological [(hour, T, Tnext, Tair, G)]."""
    steps = []
    for h in sorted(temps):
        nxt = h + timedelta(hours=1)
        if nxt in temps and h in weather:
            tair, g = weather[h]
            steps.append((h, temps[h], temps[nxt], tair, g))
    return steps


def solve3(m, v):
    """Solve a 3x3 linear system by Gaussian elimination with partial pivoting. Returns None if singular."""
    a = [row[:] + [v[i]] for i, row in enumerate(m)]
    for col in range(3):
        piv = max(range(col, 3), key=lambda r: abs(a[r][col]))
        if abs(a[piv][col]) < 1e-12:
            return None
        a[col], a[piv] = a[piv], a[col]
        for r in range(3):
            if r != col:
                f = a[r][col] / a[col][col]
                a[r] = [x - f * y for x, y in zip(a[r], a[col])]
    return tuple(a[i][3] / a[i][i] for i in range(3))


def fit(steps):
    """Least squares for dT = a*G + b*(Tair - T) + c."""
    xtx = [[0.0] * 3 for _ in range(3)]
    xty = [0.0] * 3
    for _, t, tn, tair, g in steps:
        x = (g, tair - t, 1.0)
        y = tn - t
        for i in range(3):
            xty[i] += x[i] * y
            for j in range(3):
                xtx[i][j] += x[i] * x[j]
    return solve3(xtx, xty)


def step(t, tair, g, params):
    a, b, c = params
    return t + a * g + b * (tair - t) + c


def simulate(start_hour, start_temp, hours, weather, params):
    """Free-run from a measured start through `hours` consecutive hours. Stops at a weather gap.
    Returns {hour: predicted T} including the start hour."""
    out = {start_hour: start_temp}
    t, h = start_temp, start_hour
    for _ in range(hours):
        if h not in weather:
            break
        tair, g = weather[h]
        t = step(t, tair, g, params)
        h = h + timedelta(hours=1)
        out[h] = t
    return out


def calibrate(readings, weather, tz, cfg=TwinConfig()):
    """Fit and validate. Returns TwinResult without a forecast."""
    temps = hourly_means(readings, tz)
    steps = build_steps(temps, weather)
    need = cfg.min_train_steps + cfg.min_holdout_steps
    if len(steps) < need:
        return TwinResult('insufficient', f'Needs at least {need} consecutive hourly sensor steps with weather; '
                                          f'has {len(steps)}. Keep the logger running.')
    split = int(len(steps) * 0.75)
    train, hold = steps[:split], steps[split:]
    if len(train) < cfg.min_train_steps or len(hold) < cfg.min_holdout_steps:
        return TwinResult('insufficient', 'Not enough data on both sides of the validation split yet.')
    params = fit(train)
    base = dict(n_train=len(train), n_holdout=len(hold),
                air_range=(min(s[3] for s in train), max(s[3] for s in train)),
                ghi_range=(min(s[4] for s in train), max(s[4] for s in train)))
    if params is None or not (params[0] >= 0 and 0 < params[1] < 1):
        return TwinResult('implausible', 'The fitted parameters are not physically plausible (solar gain must be '
                                         '≥ 0 and air exchange between 0 and 1 per hour), so the model is not used.',
                          params=params, **base)
    # Free-run validation over the held-out period, starting from its first measured temperature.
    h0 = hold[0][0]
    span = int((hold[-1][0] - h0).total_seconds() // 3600) + 1
    pred = simulate(h0, hold[0][1], span, weather, params)
    errors = [pred[h] - temps[h] for h in pred if h in temps and h != h0]
    if len(errors) < cfg.min_holdout_steps:
        return TwinResult('insufficient', 'Weather gaps prevent a full held-out simulation.', params=params, **base)
    mae = sum(abs(e) for e in errors) / len(errors)
    rmse = math.sqrt(sum(e * e for e in errors) / len(errors))
    base.update(params=params, holdout_mae=mae, holdout_rmse=rmse, validated_horizon_h=span)
    if mae > cfg.max_holdout_mae_c:
        return TwinResult('failed_validation', f'Held-out error {mae:.2f} °C exceeds the {cfg.max_holdout_mae_c} °C '
                                               'limit, so no forecast is shown.', **base)
    return TwinResult('ok', f'Validated on {len(errors)} held-out hours: mean absolute error {mae:.2f} °C.', **base)


def forecast(result, readings, weather, tz, now, horizon_h=72, cfg=TwinConfig()):
    """Adds an hourly forecast to a validated result, starting from the latest measured hour."""
    if not result.ok:
        return result
    temps = hourly_means(readings, tz)
    start = max(temps)
    if (hour_floor(now, tz) - start).total_seconds() / 3600 > cfg.max_start_age_hours:
        result.status, result.message = 'stale', (
            f'Latest sensor reading is older than {cfg.max_start_age_hours:g} h; forecast paused until new data arrives.')
        return result
    horizon = min(horizon_h, result.validated_horizon_h)
    pred = simulate(start, temps[start], horizon, weather, result.params)
    band = 1.96 * result.holdout_rmse
    lo_air, hi_air = result.air_range
    lo_g, hi_g = result.ghi_range
    for h in sorted(pred):
        if h <= start:
            continue
        prev = h - timedelta(hours=1)
        tair, g = weather[prev]
        ext = not (lo_air <= tair <= hi_air and lo_g <= g <= hi_g)
        result.forecast.append((h, pred[h], pred[h] - band, pred[h] + band, ext))
    return result


@dataclass
class Effect:
    status: str
    message: str
    days: int = 0
    mean_c: float = None
    ci: tuple = None
    degree_hours_avoided: float = None
    daily: list = field(default_factory=list)    # [(date, observed max, predicted max)]


def intervention_effect(readings, weather, tz, applied_at, threshold_c=30.0, cfg=TwinConfig(), min_days=3):
    """Compare measured daily peaks after an intervention with what the *pre-intervention* twin predicts
    for the same weather. Assumes nothing else changed (refill schedule, water use, sensor position)."""
    pre = [(dt, v) for dt, v in readings if dt < applied_at]
    post = [(dt, v) for dt, v in readings if dt >= applied_at]
    model = calibrate(pre, weather, tz, cfg)
    if not model.ok:
        return Effect('no_model', f'No validated pre-intervention model: {model.message}')
    temps = hourly_means(post, tz)
    by_day = {}
    for h in temps:
        by_day.setdefault(h.date(), []).append(h)
    daily, dh = [], 0.0
    for day in sorted(by_day):
        hours = sorted(by_day[day])
        if len(hours) < 18:
            continue
        pred = simulate(hours[0], temps[hours[0]], 23, weather, model.params)
        common = [h for h in hours if h in pred]
        if len(common) < 18:
            continue
        daily.append((day, max(temps[h] for h in common), max(pred[h] for h in common)))
        dh += sum(max(pred[h] - threshold_c, 0) - max(temps[h] - threshold_c, 0) for h in common)
    if len(daily) < min_days:
        return Effect('insufficient', f'Needs at least {min_days} post-intervention days with 18+ logged hours; '
                                      f'has {len(daily)}.', days=len(daily), daily=daily)
    diffs = [o - p for _, o, p in daily]
    n = len(diffs)
    mean = sum(diffs) / n
    sd = math.sqrt(sum((d - mean) ** 2 for d in diffs) / (n - 1))
    half = t_crit(n - 1) * sd / math.sqrt(n)
    return Effect('ok', f'Measured vs predicted daily peak over {n} days (pre-intervention model error '
                        f'{model.holdout_mae:.2f} °C).', days=n, mean_c=mean, ci=(mean - half, mean + half),
                  degree_hours_avoided=dh, daily=daily)
