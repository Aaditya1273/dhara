import { useEffect, useRef, useState, type ReactNode } from 'react';
import { motion, useAnimationFrame, useInView, useMotionValue, useScroll, useSpring, useTransform, useVelocity, wrap } from 'motion/react';
import { SectionHead } from '../../components/SectionHead';
import { Pause, Play } from '../../components/Icons';
import { useMotionOK } from '../../hooks/media';
import { CARDS, STATEMENTS } from './cards';
import './Trust.css';

/** An endless row. It drifts on its own, speeds up with scroll velocity and follows the scroll direction.
    Copies after the first are hidden from assistive technology. */
function Marquee({ children, speed, paused, className }: { children: ReactNode; speed: number; paused: boolean; className: string }) {
  const ref = useRef<HTMLDivElement>(null), setRef = useRef<HTMLDivElement>(null);
  const inView = useInView(ref);
  const [setW, setSetW] = useState(0);
  const x = useMotionValue(0);
  const { scrollY } = useScroll();
  const v = useSpring(useVelocity(scrollY), { damping: 50, stiffness: 400 });
  const boost = useTransform(v, [-1500, 0, 1500], [-4, 0, 4], { clamp: false });
  const dir = useRef(speed < 0 ? -1 : 1);

  useEffect(() => {
    const el = setRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setSetW(el.offsetWidth));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useAnimationFrame((_, delta) => {
    if (paused || !inView || !setW) return;
    const b = boost.get();
    if (b < 0) dir.current = -Math.sign(speed); else if (b > 0) dir.current = Math.sign(speed);
    const move = dir.current * Math.abs(speed) * (delta / 1000) * (1 + Math.abs(b));
    x.set(wrap(-setW, 0, x.get() - move));
  });

  return (
    <div ref={ref} className={`marquee ${className}`}>
      <motion.div className="marquee-track" style={{ x }}>
        <div ref={setRef} className="marquee-set">{children}</div>
        {[1, 2].map((n) => <div key={n} className="marquee-set" aria-hidden="true" inert>{children}</div>)}
      </motion.div>
    </div>
  );
}

function Cards() {
  return (
    <>
      {CARDS.map((c) => (
        <article key={c.key} className={`tcard${c.tone ? ` ${c.tone}` : ''}`}>
          <div className="tcard-visual" aria-hidden="true">{c.visual}</div>
          <h3>{c.title}</h3>
          <ul>{c.items.map((i) => <li key={i}>{i}</li>)}</ul>
        </article>
      ))}
    </>
  );
}

export function Trust() {
  const ok = useMotionOK();
  const [paused, setPaused] = useState(false);
  const [hover, setHover] = useState(false);

  return (
    <section id="trust" className="lp-section trust-sec" aria-labelledby="trust-title">
      <div className="lp-wrap trust-head">
        <SectionHead id="trust-title" index="Trust and transparency" lead="Clear about what it knows," accent="and what it doesn't." />
        {ok && (
          <button type="button" className="marquee-toggle" aria-pressed={paused} onClick={() => setPaused(!paused)}>
            {paused ? <Play /> : <Pause />}<span>{paused ? 'Play' : 'Pause'} motion</span>
          </button>
        )}
      </div>

      {ok ? (
        <div onPointerEnter={() => setHover(true)} onPointerLeave={() => setHover(false)} onFocus={() => setHover(true)} onBlur={() => setHover(false)}>
          <Marquee speed={42} paused={paused || hover} className="m-cards"><Cards /></Marquee>
          <div aria-hidden="true">
            <Marquee speed={-30} paused={paused} className="m-chips">
              {STATEMENTS.map((s) => <span key={s.t} className={`chip${s.not ? ' not' : ''}`}>{s.t}</span>)}
            </Marquee>
          </div>
        </div>
      ) : (
        <div className="lp-wrap"><div className="trust-static"><Cards /></div></div>
      )}
    </section>
  );
}
