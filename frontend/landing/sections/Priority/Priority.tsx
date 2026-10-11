import { useRef, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { data } from '../../data';
import { SectionHead } from '../../components/SectionHead';
import { Badge } from '../../components/Badge';
import { Reveal } from '../../components/Reveal';
import { Gauge } from './Gauge';
import { Instruments } from './Instruments';
import './Priority.css';

const ease = [0.16, 1, 0.3, 1] as const;

/** Example situations run through DHARA's own rule engine on the server. Choosing one moves the instruments,
    lists the rules that fired and swings the dial to the engine's level. */
export function Priority() {
  const { scenarios, cfg } = data;
  const [sel, setSel] = useState(Math.min(1, scenarios.length - 1));
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);
  const s = scenarios[sel];
  if (!s) return null;

  const onKey = (e: React.KeyboardEvent, i: number) => {
    const n = ['ArrowDown', 'ArrowRight'].includes(e.key) ? 1 : ['ArrowUp', 'ArrowLeft'].includes(e.key) ? -1 : 0;
    if (!n) return;
    e.preventDefault();
    const next = (i + n + scenarios.length) % scenarios.length;
    setSel(next); tabs.current[next]?.focus();
  };

  return (
    <section id="priority" className="lp-section alt" aria-labelledby="priority-title">
      <div className="lp-wrap">
        <SectionHead id="priority-title" index="Heat-aware testing priority" lead="From evidence to" accent="the next measurement.">
          Choose a situation. The outcome is produced by DHARA's own rule engine with its configured thresholds. It is a suggestion to measure or review, never a diagnosis.
        </SectionHead>

        <Reveal className="console">
          <div className="sc-tabs" role="tablist" aria-label="Example situations" aria-orientation="vertical">
            {scenarios.map((c, i) => (
              <button key={c.key} ref={(el) => { tabs.current[i] = el; }} role="tab" id={`sc-t-${c.key}`} aria-controls="sc-panel"
                aria-selected={i === sel} tabIndex={i === sel ? 0 : -1} onClick={() => setSel(i)} onKeyDown={(e) => onKey(e, i)}>
                {i === sel && <motion.span layoutId="sc-active" className="sc-active" transition={{ type: 'spring', stiffness: 400, damping: 34 }} />}
                <span className="sc-title">{c.title}</span>
                <span className={`sc-level lvl-${c.level}`}>{c.levelLabel}</span>
              </button>
            ))}
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
        </Reveal>
        <p className="engine-note">Thresholds used: free chlorine minimum {cfg.chlorineMin} mg/L (IS 10500:2012), stale after {cfg.chlorineMaxAgeH} h, warm water from {cfg.warmC} °C, hot forecast from {cfg.hotC} °C. Each institution can change them. The situations are illustrative inputs; the outcomes are the engine's real output for them.</p>
      </div>
    </section>
  );
}
