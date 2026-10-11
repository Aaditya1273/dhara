import { useRef } from 'react';
import { motion, useScroll, useTransform } from 'motion/react';
import { data } from '../../data';
import { useMedia, useMotionOK } from '../../hooks/media';
import './Hero.css';

const ease = [0.16, 1, 0.3, 1] as const;

/** Rooftop-tank photograph behind the headline. On wide screens the photo and copy move at different depths as the page scrolls. */
export function Hero() {
  const ref = useRef<HTMLElement>(null);
  const wide = useMedia('(min-width: 1100px)');
  const depth = useMotionOK() && wide;

  const { scrollYProgress } = useScroll({ target: ref, offset: ['start start', 'end start'] });
  const imgY = useTransform(scrollYProgress, [0, 1], ['0%', '16%']);
  const imgScale = useTransform(scrollYProgress, [0, 1], [1.04, 1.14]);
  const copyY = useTransform(scrollYProgress, [0, 1], [0, -90]);
  const copyFade = useTransform(scrollYProgress, [0, 0.7], [1, 0]);


  return (
    <section ref={ref} className="hero" aria-labelledby="hero-title">
      <motion.picture className="hero-media" style={depth ? { y: imgY, scale: imgScale } : undefined}
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 1.2, ease }}>
        <source media="(max-width: 699px)" srcSet={data.img.heroMobile} />
        <img src={data.img.hero1672} srcSet={`${data.img.hero1100} 1100w, ${data.img.hero1672} 1672w`} sizes="100vw"
          width={1672} height={941} alt="" fetchPriority="high" decoding="async" />
      </motion.picture>
      <div className="hero-veil" aria-hidden="true" />
      <svg className="hero-flow" viewBox="0 0 2880 220" preserveAspectRatio="none" aria-hidden="true" focusable="false">
        <path d="M0 140 C 240 90, 480 190, 720 140 S 1200 90, 1440 140 S 1920 190, 2160 140 S 2640 90, 2880 140" />
        <path d="M0 170 C 240 130, 480 210, 720 170 S 1200 130, 1440 170 S 1920 210, 2160 170 S 2640 130, 2880 170" />
      </svg>

      <div className="lp-wrap hero-inner">
        <motion.div className="hero-copy" style={depth ? { y: copyY, opacity: copyFade } : undefined}
          initial="hidden" animate="shown" variants={{ shown: { transition: { staggerChildren: 0.09 } } }}>
          {[
            <p key="t" className="tagline">Water · Heat · Accountability</p>,
            <p key="a" className="audience">For hostels, schools and campuses</p>,
            <h1 key="h" id="hero-title"><span>Water deserves</span> <span className="serif">more than a record.</span></h1>,
            <p key="l" className="lede">Measure changing water conditions, prioritise testing when it matters, and keep a traceable record of every response.</p>,
            <div key="c" className="hero-actions">
              <a className="btn btn-primary btn-lg" href="#priority">Explore DHARA <span className="arrow" aria-hidden="true">→</span></a>
              <a className="btn btn-ghost btn-lg" href="#workflow">See how it works</a>
            </div>,
          ].map((el) => (
            <motion.div key={el.key} variants={{ hidden: { opacity: 0, y: 28 }, shown: { opacity: 1, y: 0, transition: { duration: 0.9, ease } } }}>{el}</motion.div>
          ))}
        </motion.div>
      </div>

      <a className="hero-cue" href="#problem" aria-label="Scroll to the next section"><span /></a>
    </section>
  );
}
