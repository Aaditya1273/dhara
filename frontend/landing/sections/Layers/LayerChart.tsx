import { useRef, useState } from 'react';
import { motion, useTransform, type MotionValue } from 'motion/react';
import { useMotionOK } from '../../hooks/media';

/* Illustrative geometry (viewBox 640 × 340). Five days span x 20…630; "now" sits at x 420.
   The °C scales below only translate these illustrative curves into readable numbers for the crosshair. */
const X0 = 20, X1 = 630, NOW = 420, DAY = (X1 - X0) / 5;
const AIR = 'M20 92 C 70 82, 95 38, 140 34 S 210 88, 260 92 S 330 40, 380 32 S 460 86, 520 90 S 590 44, 630 38';
const WATER = 'M20 196 C 70 192, 100 168, 140 164 S 210 186, 260 188 S 330 162, 380 158 S 405 166, 420 170';
const MODEL = 'M420 170 C 460 158, 490 156, 520 164 S 590 182, 630 172';
const BAND = 'M420 160 C 460 146, 490 144, 520 152 S 590 170, 630 160 L630 186 C 590 196, 550 178, 520 176 S 460 172, 420 180 Z';
const WATER_AREA = `${WATER} L420 226 L20 226 Z`;
const READINGS: [number, number][] = [[60, 193], [140, 164], [220, 182], [300, 180], [380, 158]];
const CHLORINE: [number, number, string][] = [[70, 258, '0.60'], [200, 262, '0.45'], [330, 266, '0.30']];
const airC = (y: number) => 42 - (y - 32) * 0.2;
const waterC = (y: number) => 31.5 - (y - 158) * (4 / 38);

/** y of a left-to-right path at a given x, by binary search over its length. */
function yAt(path: SVGPathElement | null, x: number): number | null {
  if (!path) return null;
  let lo = 0, hi = path.getTotalLength();
  const start = path.getPointAtLength(0).x, end = path.getPointAtLength(hi).x;
  if (x < start - 0.5 || x > end + 0.5) return null;
  for (let i = 0; i < 24; i++) {
    const mid = (lo + hi) / 2;
    if (path.getPointAtLength(mid).x < x) lo = mid; else hi = mid;
  }
  return path.getPointAtLength((lo + hi) / 2).y;
}

/** A clip rectangle that grows left to right with the layer's slice of scroll progress. Clipping (not pathLength)
    keeps dotted and dashed strokes intact. */
function Wipe({ id, v, on }: { id: string; v: MotionValue<number>; on: boolean }) {
  const width = useTransform(v, [0, 1], [0, 660]);
  return <clipPath id={id}><motion.rect x="-10" y="0" height="340" style={on ? { width } : { width: 660 }} /></clipPath>;
}

export function LayerChart({ progress }: { progress: MotionValue<number> }) {
  const ok = useMotionOK();
  // Each layer draws during its own slice of the scroll; slices overlap a little so the chart feels continuous.
  const d = [
    useTransform(progress, [0, 0.28], [0, 1]),
    useTransform(progress, [0.18, 0.46], [0, 1]),
    useTransform(progress, [0.36, 0.64], [0, 1]),
    useTransform(progress, [0.54, 0.82], [0, 1]),
    useTransform(progress, [0.72, 1], [0, 1]),
  ];
  const clip = (i: number) => `url(#wipe-${i})`;

  const svgRef = useRef<SVGSVGElement>(null);
  const airRef = useRef<SVGPathElement>(null), waterRef = useRef<SVGPathElement>(null), modelRef = useRef<SVGPathElement>(null);
  const [x, setX] = useState<number | null>(null);

  const toX = (clientX: number) => {
    const svg = svgRef.current;
    if (!svg) return null;
    const pt = svg.createSVGPoint(); pt.x = clientX; pt.y = 0;
    const local = pt.matrixTransform(svg.getScreenCTM()!.inverse());
    return Math.max(X0, Math.min(X1, local.x));
  };
  const onKey = (e: React.KeyboardEvent) => {
    const step = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
    if (!step) return;
    e.preventDefault();
    setX((v) => Math.max(X0, Math.min(X1, (v ?? NOW) + step * DAY / 8)));
  };

  // Crosshair readout.
  let read: { time: string; air: string; water: string; chlorine?: string } | null = null;
  if (x !== null) {
    // Day only: the illustrative curves are not drawn to a daily cycle, so a clock time would mislead.
    const day = Math.min(5, Math.floor((x - X0) / DAY) + 1);
    const ay = yAt(airRef.current, x), wy = x <= NOW ? yAt(waterRef.current, x) : yAt(modelRef.current, x);
    const near = CHLORINE.find(([cx]) => Math.abs(cx - x) < 16);
    read = {
      time: `Day ${day}${x > NOW ? ', after now' : ''}`,
      air: ay !== null ? `${airC(ay).toFixed(1)} °C forecast` : '—',
      water: wy === null ? '—' : x <= NOW ? `${waterC(wy).toFixed(1)} °C measured` : `${waterC(wy).toFixed(1)} ± 0.8 °C estimate`,
      chlorine: near ? `${near[2]} mg/L recorded` : undefined,
    };
  }

  return (
    <div className="lchart" tabIndex={0} role="group" onKeyDown={onKey} onBlur={() => setX(null)}
      aria-label="Illustrative chart. Use the left and right arrow keys to read values at a moment in time.">
      <svg ref={svgRef} className="layer-svg" viewBox="0 0 640 340" role="img"
        aria-label="Illustration: forecast air temperature in a band above the tank; measured tank water as a solid line up to now, then a dashed estimate with a band; free-chlorine readings in their own lane; review and resolution markers along the bottom."
        onPointerMove={(e) => setX(toX(e.clientX))} onPointerLeave={() => setX(null)}>
        <defs>
          <linearGradient id="water-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#0866f5" stopOpacity=".22" /><stop offset="1" stopColor="#0866f5" stopOpacity="0" />
          </linearGradient>
          {d.map((v, i) => <Wipe key={i} id={`wipe-${i}`} v={v} on={ok} />)}
        </defs>

        {[0, 1, 2, 3, 4, 5].map((i) => <line key={i} className="grid-v" x1={X0 + i * DAY} y1="20" x2={X0 + i * DAY} y2="312" />)}
        {[0, 1, 2, 3, 4].map((i) => <text key={i} className="tick" x={X0 + i * DAY + DAY / 2} y="332" textAnchor="middle">Day {i + 1}</text>)}
        <text x="0" y="14">Outside the tank</text>
        <line className="lane" x1="0" y1="112" x2="640" y2="112" />
        <text x="0" y="132">Inside the tank</text>
        <line className="lane" x1="0" y1="226" x2="640" y2="226" />
        <text x="0" y="246">Free chlorine, own lane</text>
        <line className="lane" x1="0" y1="282" x2="640" y2="282" />
        <line className="now" x1={NOW} y1="20" x2={NOW} y2="312" /><text x={NOW + 6} y="30">now</text>

        <g className="lyr lyr-air" clipPath={clip(0)}>
          <path ref={airRef} d={AIR} className="p-air" />
          <text x="150" y="28">air (forecast)</text>
        </g>
        <g className="lyr lyr-water" clipPath={clip(1)}>
          <path d={WATER_AREA} fill="url(#water-fill)" />
          <path ref={waterRef} d={WATER} className="p-water" />
          {READINGS.map(([cx, cy]) => <circle key={cx} cx={cx} cy={cy} r="3.5" className="pt-water" />)}
          <text x="40" y="216">tank water (measured)</text>
          <circle className="now-pulse" cx={NOW} cy="170" r="5" />
        </g>
        <g className="lyr lyr-chlorine" clipPath={clip(2)}>
          {CHLORINE.map(([cx, cy, v]) => (
            <g key={cx}><path d={`M${cx} ${cy} l6 6 -6 6 -6 -6z`} className="pt-chlorine" /><text x={cx + 12} y={cy + 12}>{v}{cx === 330 ? ' mg/L' : ''}</text></g>
          ))}
        </g>
        <g className="lyr lyr-model" clipPath={clip(3)}>
          <path d={BAND} className="p-band" />
          <path ref={modelRef} d={MODEL} className="p-model" />
          <text x="470" y="140">estimate, if validated</text>
        </g>
        <g className="lyr lyr-human" clipPath={clip(4)}>
          <rect x="150" y="290" width="4" height="22" rx="1" /><text x="160" y="306">Reviewed</text>
          <rect x="560" y="290" width="4" height="22" rx="1" /><text x="570" y="306">Resolved</text>
        </g>

        {x !== null && <line className="cross" x1={x} y1="20" x2={x} y2="312" />}
      </svg>
      {read && x !== null && (
        <div className={`readout${x > 430 ? ' left' : ''}`} style={{ left: `${(x / 640) * 100}%` }} aria-live="polite">
          <b>{read.time}</b>
          <span className="r-air">Air {read.air}</span>
          <span className="r-water">Tank {read.water}</span>
          {read.chlorine && <span className="r-chlorine">Chlorine {read.chlorine}</span>}
          <small>Illustrative values</small>
        </div>
      )}
    </div>
  );
}
