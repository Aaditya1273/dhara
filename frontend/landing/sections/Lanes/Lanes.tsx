import { useRef, useState } from 'react';
import { motion, useMotionValue, useMotionValueEvent, useScroll, useTransform, type MotionValue } from 'motion/react';
import { SectionHead } from '../../components/SectionHead';
import { Check } from '../../components/Icons';
import { usePinned } from '../../hooks/media';
import './Lanes.css';

const LANES = [
  { key: 'm', title: 'Maintenance evidence', sub: 'What work was done, and who checked it', nodes: [
    ['Work submitted', "Claimed work date and the server's own submission time, kept separately."],
    ['Photos and documents', 'Stored privately, each with a SHA-256 fingerprint.'],
    ['Warden decision', 'Accept, reject or ask for more, with a reason. Never by the submitter.'],
    ['Correction, not edit', 'Reviewed events stay unchanged; a correction is a new event.'],
  ] },
  { key: 'q', title: 'Water-quality observations', sub: 'What was measured, how and by whom', nodes: [
    ['Field reading', 'Temperature or free chlorine with method, time and source: a person or a probe.'],
    ['Strip photo', 'Optional evidence image with its own digest.'],
    ['Laboratory report', 'Sample date and parameters exactly as the report states.'],
    ['Institution review', 'Marked reviewed by a warden. Still not independent verification.'],
  ] },
] as const;

/** Both lanes share one fill value, so they advance side by side and their steps light up together. */
function Board({ fill, done }: { fill: MotionValue<number>; done: boolean }) {
  const litFor = (v: number) => (v <= 0 ? -1 : Math.floor(v * 3 + 0.001));
  const [lit, setLit] = useState(() => litFor(fill.get()));
  useMotionValueEvent(fill, 'change', (v) => setLit(litFor(v)));
  const left = useTransform(fill, (v) => `${v * 100}%`);

  return (
    <div className="lanes">
      {LANES.map((lane, li) => (
        <div key={lane.key} className={`ev-lane ${lane.key}`}>
          <div className="lane-title">{lane.title}<small>{lane.sub}</small></div>
          <ol className="lane-nodes">
            <li className="lane-line" aria-hidden="true">
              <motion.span className="lane-fill" style={{ scaleX: fill }} />
              <motion.span className="lane-pulse" style={{ left }} />
            </li>
            {lane.nodes.map(([h, p], i) => (
              <li key={h} className={`node${i <= lit ? ' is-on' : ''}`}>
                <span className="dot">{i + 1}</span>
                <h3>{h}</h3>
                <p>{p}</p>
              </li>
            ))}
          </ol>
          {li === 0 && <p className="divider">The lanes never merge</p>}
        </div>
      ))}
      <div className={`audit-end${done ? ' is-on' : ''}`}>
        <span className="audit-check" aria-hidden="true"><Check /></span>
        <div><strong>Both lanes end in one audit trail</strong>
          <p>Every entry records who acted, what changed and the server time. An ordinary log without edit screens, not a tamper-proof ledger.</p></div>
        <a className="btn btn-ghost" href="#workflow">See the workflow</a>
      </div>
    </div>
  );
}

export function Lanes() {
  const pinned = usePinned();
  const track = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: track, offset: ['start start', 'end end'] });
  const scrolled = useTransform(scrollYProgress, [0.06, 0.74], [0, 1], { clamp: true });
  const full = useMotionValue(1);
  const [done, setDone] = useState(false);
  useMotionValueEvent(scrollYProgress, 'change', (p) => setDone(p > 0.82));

  const head = (
    <SectionHead id="lanes-title" index="Two lanes of evidence" lead="Connected by accountability." accent="Never merged." className="compact">
      A completed repair or a clean photograph is not proof of potable water. DHARA keeps maintenance evidence and water-quality observations apart, and lets both end in one audit trail.
    </SectionHead>
  );

  return (
    <section id="evidence" className="lp-section lanes-sec" aria-labelledby="lanes-title">
      {pinned ? (
        <div ref={track} className="pin-track" style={{ height: '320vh' }}>
          <div className="pin-stage"><div className="lp-wrap">{head}<Board fill={scrolled} done={done} /></div></div>
        </div>
      ) : (
        <div className="lp-wrap">{head}<Board fill={full} done /></div>
      )}
    </section>
  );
}
