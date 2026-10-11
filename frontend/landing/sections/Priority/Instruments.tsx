import { motion } from 'motion/react';
import { data } from '../../data';
import type { Scenario } from '../../types';
import { Drop, Sun, Thermo } from '../../components/Icons';

const spring = { type: 'spring', stiffness: 120, damping: 18 } as const;
const clamp01 = (v: number) => Math.max(0, Math.min(1, v));

/** The three inputs the rule engine evaluated, drawn against the configured thresholds.
    Captions use the exact evidence strings the server produced. */
export function Instruments({ s }: { s: Scenario }) {
  const { cfg } = data;
  const { chlorine, chlorineAgeH, waterC, airMaxC } = s.inputs;
  const [clText, wtText, airText] = s.evidence.map(([, v]) => v);

  return (
    <div className="instruments">
      {/* Free chlorine: a vial filled to the reading (scale 0–1 mg/L), the configured minimum as a line, reading age as a ring. */}
      <figure className={`inst${chlorine === null ? ' is-empty' : ''}`}>
        <figcaption><span className="i-ico chlorine"><Drop /></span>Free chlorine</figcaption>
        <div className="inst-body">
          <svg className="vial" viewBox="0 0 60 120" aria-hidden="true">
            <defs><clipPath id="vial-clip"><rect x="14" y="8" width="32" height="104" rx="14" /></clipPath></defs>
            <g clipPath="url(#vial-clip)">
              <rect x="14" y="8" width="32" height="104" className="vial-bg" />
              <motion.rect x="14" width="32" className="vial-fill" initial={false}
                animate={{ y: 112 - 104 * clamp01(chlorine ?? 0), height: 104 * clamp01(chlorine ?? 0) }} transition={spring} />
            </g>
            <rect x="14" y="8" width="32" height="104" rx="14" className="vial-glass" />
            <line x1="8" x2="52" y1={112 - 104 * cfg.chlorineMin} y2={112 - 104 * cfg.chlorineMin} className="thr" />
          </svg>
          <div className="inst-read">
            <strong>{chlorine === null ? 'No reading' : <>{chlorine.toFixed(2)}<small> mg/L</small></>}</strong>
            <span className="thr-note">Minimum {cfg.chlorineMin} mg/L</span>
            {chlorineAgeH !== null && (
              <div className="age">
                <svg viewBox="0 0 36 36" aria-hidden="true">
                  <circle cx="18" cy="18" r="15" className="age-bg" />
                  <motion.circle cx="18" cy="18" r="15" className="age-fg" initial={false}
                    animate={{ pathLength: clamp01(chlorineAgeH / cfg.chlorineMaxAgeH) }} transition={spring} />
                </svg>
                <span>{Math.round(chlorineAgeH)} h old<br /><small>stale after {cfg.chlorineMaxAgeH} h</small></span>
              </div>
            )}
          </div>
        </div>
        <p className="inst-src">{clText}</p>
      </figure>

      {/* Tank water: a thermometer on a 15–40 °C scale with the configured warm-water threshold. */}
      <figure className={`inst${waterC === null ? ' is-empty' : ''}`}>
        <figcaption><span className="i-ico water"><Thermo /></span>Tank-water temperature</figcaption>
        <div className="inst-body">
          <svg className="thermo" viewBox="0 0 60 120" aria-hidden="true">
            <rect x="24" y="6" width="12" height="90" rx="6" className="vial-bg" />
            <motion.rect x="24" width="12" rx="6" className="thermo-fill" initial={false}
              animate={{ y: 96 - 90 * clamp01(((waterC ?? 15) - 15) / 25), height: 90 * clamp01(((waterC ?? 15) - 15) / 25) + 6 }} transition={spring} />
            <circle cx="30" cy="104" r="11" className={waterC === null ? 'vial-bg' : 'thermo-bulb'} />
            <line x1="14" x2="46" y1={96 - 90 * ((cfg.warmC - 15) / 25)} y2={96 - 90 * ((cfg.warmC - 15) / 25)} className="thr" />
          </svg>
          <div className="inst-read">
            <strong>{waterC === null ? 'No reading' : <>{waterC.toFixed(1)}<small> °C</small></>}</strong>
            <span className="thr-note">Warm from {cfg.warmC} °C</span>
          </div>
        </div>
        <p className="inst-src">{wtText}</p>
      </figure>

      {/* Forecast air: a 25–45 °C bar with the configured hot-forecast threshold. Air, not tank water. */}
      <figure className="inst">
        <figcaption><span className="i-ico air"><Sun /></span>Forecast air, next days</figcaption>
        <div className="inst-body col">
          <strong className="air-v">{airMaxC.toFixed(0)}<small> °C max</small></strong>
          <div className="heat-bar" aria-hidden="true">
            <motion.span className="heat-fill" initial={false} animate={{ width: `${clamp01((airMaxC - 25) / 20) * 100}%` }} transition={spring} />
            <i className="heat-thr" style={{ left: `${((cfg.hotC - 25) / 20) * 100}%` }} />
          </div>
          <span className="thr-note">Hot forecast from {cfg.hotC} °C. This is air, not tank water.</span>
        </div>
        <p className="inst-src">{airText}</p>
      </figure>
    </div>
  );
}
