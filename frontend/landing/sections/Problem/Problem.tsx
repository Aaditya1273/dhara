import { useRef } from 'react';
import { motion, useScroll, useTransform } from 'motion/react';
import { SectionHead } from '../../components/SectionHead';
import { useMotionOK } from '../../hooks/media';
import './Problem.css';

const QUESTIONS = [
  ['How warm is the water today?', 'Rooftop tanks heat up; nobody measured.'],
  ['Is any free chlorine left?', 'No reading, no time, no method.'],
  ['Did anyone check the evidence?', 'Photos sit in a phone gallery.'],
  ['What did the lab report, and when?', 'The PDF is in an email thread.'],
] as const;

/** A paper register entry with a stamp, and the four questions it cannot answer, which drift out of it on scroll. */
export function Problem() {
  const ref = useRef<HTMLDivElement>(null);
  const ok = useMotionOK();
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start end', 'end start'] });
  const tilt = useTransform(scrollYProgress, [0, 1], [-5, 3]);
  const lift = useTransform(scrollYProgress, [0, 1], [60, -60]);

  return (
    <section id="problem" className="lp-section alt" aria-labelledby="problem-title">
      <div className="lp-wrap problem">
        <SectionHead id="problem-title" index="The problem" lead="A cleaning record" accent="can't see inside the tank.">
          Registers say when someone cleaned. They don't say how warm the water is now, whether any chlorine is left, who checked the evidence, or what a laboratory found.
        </SectionHead>

        <div ref={ref} className="problem-scene">
          <motion.div className="register" style={ok ? { rotate: tilt, y: lift } : undefined} aria-label="Example of a paper register entry" role="group">
            <motion.span className="stamp" initial={{ opacity: 0, scale: 2.4, rotate: -18 }} whileInView={{ opacity: 1, scale: 1, rotate: -8 }}
              viewport={{ once: true, amount: 0.6 }} transition={{ type: 'spring', stiffness: 380, damping: 18, delay: 0.3 }}>CLEANED</motion.span>
            <p className="hand title">Tank A, Block A</p>
            <p className="hand">12 March. Drained and scrubbed.</p>
            <p className="hand faint">Signed, maintenance team</p>
            <p className="register-gap">No temperature. No chlorine. No reviewer. No lab.</p>
          </motion.div>

          <ul className="questions" aria-label="What the register cannot answer">
            {QUESTIONS.map(([q, a], i) => (
              <motion.li key={q} initial={{ opacity: 0, x: -60, y: 20, rotate: -4 }} whileInView={{ opacity: 1, x: 0, y: 0, rotate: 0 }}
                viewport={{ once: true, margin: '0px 0px -12% 0px' }} transition={{ duration: 0.9, delay: 0.15 + i * 0.12, ease: [0.16, 1, 0.3, 1] }}>
                <span className="q-mark" aria-hidden="true">?</span>
                <strong>{q}</strong><span>{a}</span>
              </motion.li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
