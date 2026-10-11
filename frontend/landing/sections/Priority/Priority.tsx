import { useRef, useState } from 'react';
import { AnimatePresence, motion, useMotionValue, useMotionValueEvent, useScroll, useTransform, type MotionValue } from 'motion/react';
import { data } from '../../data';
import { SectionHead } from '../../components/SectionHead';
import { Badge } from '../../components/Badge';
import { usePinned } from '../../hooks/media';
import { Gauge } from './Gauge';
import { Instruments } from './Instruments';
import './Priority.css';

const ease = [0.16, 1, 0.3, 1] as const;
const VH_PER_SITUATION = 70;

/** Situations on the left, the engine at work on the right. `segment` (0–1) fills the active situation's bar. */
function Console({ sel, onSelect, segment }: { sel: number; onSelect: (i: number) => void; segment: MotionValue<number> }) {
  const { scenarios } = data;
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);
  const s = scenarios[sel];
  const onKey = (e: React.KeyboardEvent, i: number) => {
    const n = ['ArrowDown', 'ArrowRight'].includes(e.key) ? 1 : ['ArrowUp', 'ArrowLeft'].includes(e.key) ? -1 : 0;
    if (!n) return;
    e.preventDefault();
    const next = (i + n + scenarios.length) % scenarios.length;
    onSelect(next); tabs.current[next]?.focus();
  };

  return (
    <div className="console">
      <div className="sc-tabs" role="tablist" aria-label="Example situations" aria-orientation="vertical">
        {scenarios.map((c, i) => (
          <button key={c.key} ref={(el) => { tabs.current[i] = el; }} role="tab" id={`sc-t-${c.key}`} aria-controls="sc-panel"
            aria-selected={i === sel} tabIndex={i === sel ? 0 : -1} onClick={() => onSelect(i)} onKeyDown={(e) => onKey(e, i)}>
            {i === sel && <motion.span layoutId="sc-active" className="sc-active" transition={{ type: 'spring', stiffness: 400, damping: 34 }} />}
            <span className="sc-step">{String(i + 1).padStart(2, '0')}</span>
            <span className="sc-title">{c.title}</span>
            <span className={`sc-level lvl-${c.level}`}>{c.levelLabel}</span>
            <span className="sc-progress" aria-hidden="true">
              <motion.i style={{ scaleX: i === sel ? segment : i < sel ? 1 : 0 }} />
            </span>
          </button>
        ))}
        <p className="sc-hint">Scroll to step through the situations, or choose one.</p>
      </div>

      <div className="sc-panel" role="tabpanel" id="sc-panel" aria-labelledby={`sc-t-${s.key}`}>
        <Instruments s={s} />
        <div className="beam" aria-hidden="true"><span /></div>
        <div className="verdict">
          <div className="rules-card">
            <h3>Rules that fired</h3>
            <AnimatePresence mode="wait">
              <motion.ul key={s.key} className="rules" initial="hidden" animate="shown" exit={{ opacity: 0, transition: { duration: 0.15 } }}
                variants={{ shown: { transition: { staggerChildren: 0.12 } } }}>
                {(s.reasons.length ? s.reasons : ['No rule fired: fresh readings inside the configured thresholds.']).map((r) => (
                  <motion.li key={r} variants={{ hidden: { opacity: 0, x: -14 }, shown: { opacity: 1, x: 0, transition: { duration: 0.5, ease } } }}>{r}</motion.li>
                ))}
                {s.context.map((c) => (
                  <motion.li key={c} className="ctx" variants={{ hidden: { opacity: 0, x: -14 }, shown: { opacity: 1, x: 0, transition: { duration: 0.5, ease } } }}>{c}</motion.li>
                ))}
              </motion.ul>
            </AnimatePresence>
          </div>
          <div className={`outcome lvl-${s.level}`}>
            <h3>Suggested next action</h3>
            <Gauge level={s.level} />
            <AnimatePresence mode="wait">
              <motion.div key={s.key} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.4, ease }}>
                <Badge tone={s.levelTone}>{s.levelLabel}</Badge>
                <p className="action">{s.actionLabel}</p>
                <p className="follow">{s.actionable ? `DHARA opens one follow-up for the tank's responsible person, due ${s.due}. A person records the result.` : 'No follow-up is opened.'}</p>
              </motion.div>
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  );
}

const Head = ({ compact }: { compact?: boolean }) => (
  <SectionHead id="priority-title" index="Heat-aware testing priority" lead="From evidence to" accent="the next measurement." className={compact ? 'compact' : ''}>
    Each situation runs through DHARA's own rule engine with its configured thresholds. The outcome is a suggestion to measure or review, never a diagnosis.
  </SectionHead>
);

const Note = () => {
  const { cfg } = data;
  return <p className="engine-note">Thresholds used: free chlorine minimum {cfg.chlorineMin} mg/L (IS 10500:2012), stale after {cfg.chlorineMaxAgeH} h, warm water from {cfg.warmC} °C, hot forecast from {cfg.hotC} °C. Each institution can change them. The situations are illustrative inputs; the outcomes are the engine's real output for them.</p>;
};

/** Pinned: the console holds still and scrolling advances one situation at a time. Choosing one jumps the scroll there. */
function Pinned() {
  const n = data.scenarios.length;
  const track = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: track, offset: ['start start', 'end end'] });
  const [sel, setSel] = useState(0);
  useMotionValueEvent(scrollYProgress, 'change', (p) => setSel(Math.min(n - 1, Math.max(0, Math.floor(p * n)))));
  const segment = useTransform(scrollYProgress, (p) => (p >= 1 ? 1 : (p * n) % 1));

  const goTo = (i: number) => {
    const el = track.current;
    if (!el) return;
    const top = el.getBoundingClientRect().top + window.scrollY;
    window.scrollTo({ top: top + ((i + 0.5) / n) * (el.offsetHeight - window.innerHeight), behavior: 'smooth' });
  };

  return (
    <div ref={track} className="pin-track" style={{ height: `${100 + n * VH_PER_SITUATION}vh` }}>
      <div className="pin-stage"><div className="lp-wrap"><Head compact /><Console sel={sel} onSelect={goTo} segment={segment} /><Note /></div></div>
    </div>
  );
}

/** Small screens and reduced motion: the same console, chosen by hand. */
function Manual() {
  const [sel, setSel] = useState(Math.min(1, data.scenarios.length - 1));
  const full = useMotionValue(1);
  return <div className="lp-wrap"><Head /><Console sel={sel} onSelect={setSel} segment={full} /><Note /></div>;
}

export function Priority() {
  const pinned = usePinned();
  if (!data.scenarios?.length) return null;
  return (
    <section id="priority" className={`lp-section alt prio-sec${pinned ? ' is-pinned' : ''}`} aria-labelledby="priority-title">
      {pinned ? <Pinned /> : <Manual />}
    </section>
  );
}
