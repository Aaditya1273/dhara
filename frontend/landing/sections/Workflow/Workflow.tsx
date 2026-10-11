import { useRef, useState } from 'react';
import { AnimatePresence, motion, useMotionValueEvent, useScroll, useTransform } from 'motion/react';
import { SectionHead } from '../../components/SectionHead';
import { Badge } from '../../components/Badge';
import { Reveal } from '../../components/Reveal';
import { usePinned } from '../../hooks/media';
import { STEPS, type Step } from './steps';
import { SCREENS } from './StepScreens';
import './Workflow.css';

const ease = [0.16, 1, 0.3, 1] as const;
const VH_PER_STEP = 75;

function Keeps({ step }: { step: Step }) {
  return (
    <div className="keeps">
      {step.keeps.badges.map(([tone, label], i) => (
        <span key={label} className="keeps-item">{i > 0 && <span className="then">then</span>}<Badge tone={tone}>{label}</Badge></span>
      ))}
      {step.keeps.note && <span>{step.keeps.note}</span>}
    </div>
  );
}

const head = (
  <SectionHead id="workflow-title" index="From observation to resolution" lead="Six steps." accent="Each one leaves a trace." className="compact" />
);

/** Pinned story: the stage holds still while scrolling advances one step at a time. */
function Pinned() {
  const track = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: track, offset: ['start start', 'end end'] });
  const [idx, setIdx] = useState(0);
  useMotionValueEvent(scrollYProgress, 'change', (p) => setIdx(Math.min(STEPS.length - 1, Math.max(0, Math.floor(p * STEPS.length)))));
  const railFill = useTransform(scrollYProgress, [0, 1], [0, 1]);
  const drift = useTransform(scrollYProgress, [0, 1], ['4%', '-46%']);
  const step = STEPS[idx], Screen = SCREENS[idx];

  const goTo = (i: number) => {
    const el = track.current;
    if (!el) return;
    const top = el.getBoundingClientRect().top + window.scrollY;
    window.scrollTo({ top: top + ((i + 0.5) / STEPS.length) * (el.offsetHeight - window.innerHeight), behavior: 'smooth' });
  };

  return (
    <div ref={track} className="pin-track" style={{ height: `${100 + STEPS.length * VH_PER_STEP}vh` }}>
      <div className="pin-stage">
        <motion.p className="wf-ghost" style={{ x: drift }} aria-hidden="true">Measure · Prioritise · Record · Review · Follow up · Verify</motion.p>
        <div className="lp-wrap wf">
          <div className="wf-copy">
            {head}
            <div className="wf-num" aria-hidden="true">
              <AnimatePresence mode="popLayout" initial={false}>
                <motion.span key={idx} initial={{ y: '100%', opacity: 0 }} animate={{ y: '0%', opacity: 1 }} exit={{ y: '-100%', opacity: 0 }} transition={{ duration: 0.6, ease }}>
                  {String(idx + 1).padStart(2, '0')}
                </motion.span>
              </AnimatePresence>
              <small>/ 06</small>
            </div>
            <AnimatePresence mode="wait" initial={false}>
              <motion.div key={idx} className="wf-text" aria-live="polite"
                initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -12 }} transition={{ duration: 0.45, ease }}>
                <h3>{step.title}</h3>
                <p>{step.text}</p>
                <Keeps step={step} />
              </motion.div>
            </AnimatePresence>
          </div>

          <div className="wf-visual">
            <div className="device">
              <div className="device-bar" aria-hidden="true"><i /><i /><i /><span>dhara · {step.short.toLowerCase()}</span></div>
              <AnimatePresence mode="wait" initial={false}>
                <motion.div key={idx} className="device-screen" aria-hidden="true"
                  initial={{ opacity: 0, scale: 0.97, filter: 'blur(6px)' }} animate={{ opacity: 1, scale: 1, filter: 'blur(0px)' }}
                  exit={{ opacity: 0, scale: 1.02, filter: 'blur(6px)' }} transition={{ duration: 0.45, ease }}>
                  <Screen />
                </motion.div>
              </AnimatePresence>
            </div>
            <span className="example-tag">Example screens, simplified</span>
          </div>

          <nav className="wf-rail" aria-label="Workflow steps">
            <div className="rail-track" aria-hidden="true"><motion.span style={{ scaleX: railFill }} /></div>
            {STEPS.map((s, i) => (
              <button key={s.title} type="button" className={i === idx ? 'is-on' : i < idx ? 'is-done' : ''} aria-current={i === idx ? 'step' : undefined} onClick={() => goTo(i)}>
                <span className="r-num">{i + 1}</span>{s.short}
              </button>
            ))}
          </nav>
        </div>
      </div>
    </div>
  );
}

/** Small screens and reduced motion: the same steps as a plain list, each with its example screen. */
function Stacked() {
  return (
    <div className="lp-wrap">
      {head}
      <ol className="wf-list">
        {STEPS.map((s, i) => {
          const Screen = SCREENS[i];
          return (
            <li key={s.title}>
              <Reveal className="wf-item">
                <div className="wf-item-text"><span className="wf-item-num">{String(i + 1).padStart(2, '0')}</span><h3>{s.title}</h3><p>{s.text}</p><Keeps step={s} /></div>
                <div className="device small" aria-hidden="true"><div className="device-screen"><Screen /></div></div>
              </Reveal>
            </li>
          );
        })}
      </ol>
      <span className="example-tag">Example screens, simplified</span>
    </div>
  );
}

export function Workflow() {
  const pinned = usePinned();
  return (
    <section id="workflow" className={`lp-section alt wf-sec${pinned ? ' is-pinned' : ''}`} aria-labelledby="workflow-title">
      {pinned ? <Pinned /> : <Stacked />}
    </section>
  );
}
