import { useEffect, useState } from 'react';
import { useMotionValueEvent, useSpring } from 'motion/react';
import type { Level } from '../../types';
import { useMotionOK } from '../../hooks/media';

/* Calm to urgent, left to right. */
const ORDER: Level[] = ['none', 'low', 'medium', 'high', 'urgent'];
const LABEL: Record<Level, string> = { none: 'None', low: 'Low', medium: 'Medium', high: 'High', urgent: 'Urgent' };
const COLOR: Record<Level, string> = { none: '#16a34a', low: '#94a3b8', medium: '#0866f5', high: '#d97706', urgent: '#b91c1c' };
const R = 80, CX = 100, CY = 100, SPAN = 180 / ORDER.length;

const at = (deg: number, r: number) => [CX + r * Math.cos((deg * Math.PI) / 180), CY - r * Math.sin((deg * Math.PI) / 180)];
function arc(i: number) {
  const [x0, y0] = at(180 - i * SPAN - 1.5, R), [x1, y1] = at(180 - (i + 1) * SPAN + 1.5, R);
  return `M${x0.toFixed(2)} ${y0.toFixed(2)} A${R} ${R} 0 0 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`;
}

/** Semicircular dial; the needle swings to the level DHARA's rule engine returned.
    A spring drives the angle, applied as SVG rotate(angle cx cy) so the pivot is always the dial centre. */
export function Gauge({ level }: { level: Level }) {
  const i = ORDER.indexOf(level);
  const target = -90 + (i + 0.5) * SPAN;
  const spring = useSpring(-90, { stiffness: 90, damping: 11, mass: 0.9 });
  const [deg, setDeg] = useState(-90);
  useMotionValueEvent(spring, 'change', setDeg);
  const ok = useMotionOK();
  useEffect(() => { if (ok) spring.set(target); else spring.jump(target); }, [spring, target, ok]);
  return (
    <svg className="gauge" viewBox="-12 -6 224 124" aria-hidden="true">
      {ORDER.map((l, k) => <path key={l} d={arc(k)} stroke={COLOR[l]} className={`g-seg${k === i ? ' on' : ''}`} />)}
      {ORDER.map((l, k) => {
        const [x, y] = at(180 - (k + 0.5) * SPAN, R + 17);
        return <text key={l} x={x} y={y} textAnchor="middle" dominantBaseline="middle" className={`g-label${k === i ? ' on' : ''}`}>{LABEL[l]}</text>;
      })}
      <g className="g-needle" transform={`rotate(${deg.toFixed(2)} ${CX} ${CY})`}>
        <path d={`M${CX - 3.5} ${CY} L${CX} ${CY - R + 14} L${CX + 3.5} ${CY} Z`} />
      </g>
      <circle cx={CX} cy={CY} r="8" className="g-hub" />
      <circle cx={CX} cy={CY} r="3" fill={COLOR[level]} />
    </svg>
  );
}
