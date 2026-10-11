import { useRef } from 'react';
import { motion, useScroll, useTransform } from 'motion/react';
import { data } from '../../data';
import { Reveal } from '../../components/Reveal';
import { useMotionOK } from '../../hooks/media';
import './Closing.css';

/** Blue closing band. Concentric ripples widen as the band scrolls into view. */
export function Closing() {
  const ref = useRef<HTMLElement>(null);
  const ok = useMotionOK();
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start end', 'end start'] });
  const scale = useTransform(scrollYProgress, [0, 1], [0.7, 1.35]);
  const { urls } = data;

  return (
    <section ref={ref} className="closing" aria-labelledby="close-title">
      <motion.div className="ripples" style={ok ? { scale } : undefined} aria-hidden="true"><i /><i /><i /><i /></motion.div>
      <div className="lp-wrap">
        <Reveal>
          <h2 id="close-title">Start with <span className="serif">one tank.</span></h2>
          <p className="lede">Register your institution, add a tank, print its QR code and record the first measurement. It takes a few minutes.</p>
          <div className="hero-actions">
            {data.authenticated ? <a className="btn btn-primary btn-lg" href={urls.dashboard}>Open dashboard</a> : (
              <><a className="btn btn-primary btn-lg" href={urls.register}>Register your institution</a><a className="btn btn-ghost btn-lg" href={urls.login}>Sign in</a></>
            )}
            {data.demoQrUrl && <a className="btn btn-ghost btn-lg" href={data.demoQrUrl}>See a live tank page</a>}
          </div>
        </Reveal>
      </div>
    </section>
  );
}
