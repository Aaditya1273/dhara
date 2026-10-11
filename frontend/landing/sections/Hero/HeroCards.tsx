import type { ReactNode } from 'react';
import { motion, useTransform, type MotionValue } from 'motion/react';
import { data } from '../../data';
import { Badge } from '../../components/Badge';
import { Alert, Drop, QrGlyph, Sun, Thermo } from '../../components/Icons';

type Depth = { depth: boolean; scroll: MotionValue<number>; px: MotionValue<number>; py: MotionValue<number> };

/** One floating card. `z` is its depth: deeper cards rise faster on scroll and follow the pointer more. */
function Float({ z, delay, className, children, ...m }: Depth & { z: number; delay: number; className: string; children: ReactNode }) {
  const y = useTransform([m.scroll, m.py], ([s, p]: number[]) => -s * 260 * z + p * 12 * z);
  const x = useTransform(m.px, (p) => p * 14 * z);
  return (
    <motion.div className={`hs ${className}`} style={m.depth ? { x, y } : undefined}>
      <motion.div initial={{ opacity: 0, y: 32, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.9, delay, ease: [0.16, 1, 0.3, 1] }}>
        {children}
      </motion.div>
    </motion.div>
  );
}

/** Every value here is illustrative demo data; the screen-reader caption says so. */
export function HeroCards(m: Depth) {
  return (
    <div className="hero-stage" role="group" aria-labelledby="hs-cap">
      <p id="hs-cap" className="sr-only">Example readings with illustrative demo data. Tank water measured at 31.4 °C by an in-tank probe at 14:20. Outdoor air forecast up to 41 °C, which is air, not tank water. Free chlorine recorded at 0.30 mg/L yesterday at 08:10, 30 hours old. DHARA suggests repeating the chlorine measurement.</p>

      <Float {...m} z={1.1} delay={0.5} className="hs-water">
        <article className="mcard" aria-hidden="true">
          <header><span className="mcard-ico water"><Thermo /></span>Tank water temperature</header>
          <p className="mcard-v">31.4<small>°C</small></p>
          <svg className="mcard-spark" viewBox="0 0 160 36">
            <motion.path className="spark-line" d="M2 30 C 20 28, 32 20, 48 21 S 76 27, 92 18 S 124 10, 140 12 S 152 8, 158 6"
              initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 1.4, delay: 1, ease: 'easeOut' }} />
            <motion.circle className="spark-dot" cx="158" cy="6" r="3" initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ delay: 2.3 }} />
          </svg>
          <p className="mcard-src"><Badge tone="good">Fresh</Badge> In-tank probe, measured 14:20</p>
        </article>
      </Float>

      <Float {...m} z={0.6} delay={0.62} className="hs-air">
        <article className="mcard" aria-hidden="true">
          <header><span className="mcard-ico air"><Sun /></span>Outdoor air forecast</header>
          <p className="mcard-v air">41<small>°C max</small></p>
          <svg className="mcard-spark" viewBox="0 0 160 36"><path className="spark-air" d="M2 30 C 30 30, 46 8, 80 6 S 130 24, 158 28" /></svg>
          <p className="mcard-src">Weather forecast, today. Air, not tank water.</p>
        </article>
      </Float>

      <Float {...m} z={1.5} delay={0.74} className="hs-chlorine">
        <article className="mcard" aria-hidden="true">
          <header><span className="mcard-ico chlorine"><Drop /></span>Free chlorine (residual)</header>
          <p className="mcard-v">0.30<small>mg/L</small></p>
          <p className="mcard-src"><Badge tone="warn">30 h old</Badge> DPD strip, yesterday 08:10</p>
        </article>
      </Float>

      <Float {...m} z={0.85} delay={0.9} className="hs-priority">
        <article className="mcard" aria-hidden="true">
          <header><span className="mcard-ico warn"><Alert /></span>Testing priority <Badge tone="info">Medium</Badge></header>
          <p className="mcard-title">Repeat the chlorine measurement</p>
          <p className="mcard-src">Latest reading is 30 h old and the tank sits in full sun during a hot forecast.</p>
        </article>
      </Float>

      {data.demoQrUrl && (
        <Float {...m} z={1.25} delay={1.02} className="hs-qr">
          <a className="mcard qr-card" href={data.demoQrUrl}>
            <span className="qr-glyph" aria-hidden="true"><QrGlyph /></span>
            <span><strong>TANK-A</strong><span className="mcard-src">Demo hostel, Block A</span><span className="qr-link">View public record</span></span>
          </a>
        </Float>
      )}
    </div>
  );
}
