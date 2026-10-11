import { motion } from 'motion/react';
import type { Level } from '../../types';

/* Calm to urgent, left to right. */
const ORDER: Level[] = ['none', 'low', 'medium', 'high', 'urgent'];
const COLOR: Record<Level, string> = { none: '#16a34a', low: '#94a3b8', medium: '#0866f5', high: '#d97706', urgent: '#b91c1c' };
const R = 80, CX = 100, CY = 100, SPAN = 180 / ORDER.length;

const pt = (deg: number) => [CX + R * Math.cos((deg * Math.PI) / 180), CY - R * Math.sin((deg * Math.PI) / 180)];
function arc(i: number) {
  const [x0, y0] = pt(180 - i * SPAN - 1.5), [x1, y1] = pt(180 - (i + 1) * SPAN + 1.5);
  return `M${x0.toFixed(2)} ${y0.toFixed(2)} A${R} ${R} 0 0 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`;
}

/** Semicircular dial; the needle springs to the level DHARA's rule engine returned. */
export function Gauge({ level }: { level: Level }) {
  const i = ORDER.indexOf(level);
  const rotate = -90 + (i + 0.5) * SPAN;
  return (
    <svg className="gauge" viewBox="0 0 200 116" aria-hidden="true">
      {ORDER.map((l, k) => (
        <path key={l} d={arc(k)} stroke={COLOR[l]} className={`g-seg${k === i ? ' on' : ''}`} />
      ))}
      {ORDER.map((l, k) => {
        const [x, y] = [CX + (R - 26) * Math.cos(((180 - (k + 0.5) * SPAN) * Math.PI) / 180), CY - (R - 26) * Math.sin(((180 - (k + 0.5) * SPAN) * Math.PI) / 180)];
        return <circle key={l} cx={x} cy={y} r="1.6" className="g-tick" />;
      })}
      <motion.g style={{ originX: `${CX}px`, originY: `${CY}px` }} initial={{ rotate: -90 }} animate={{ rotate }}
        transition={{ type: 'spring', stiffness: 90, damping: 11, mass: 0.9 }}>
        <path d={`M${CX - 3.5} ${CY} L${CX} ${CY - R + 12} L${CX + 3.5} ${CY} Z`} className="g-needle" />
      </motion.g>
      <circle cx={CX} cy={CY} r="8" className="g-hub" />
      <circle cx={CX} cy={CY} r="3" fill={COLOR[level]} />
    </svg>
  );
}
