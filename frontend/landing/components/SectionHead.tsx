import { motion } from 'motion/react';
import { Fragment, type ReactNode } from 'react';

const ease = [0.16, 1, 0.3, 1] as const;

/** Section label, a serif headline whose words rise out of a mask one after another, and an optional lede. */
export function SectionHead({ id, index, lead, accent, children, className = '' }:
  { id: string; index: string; lead: string; accent: string; children?: ReactNode; className?: string }) {
  const words = [...lead.split(' ').map((w) => ({ w, a: false })), ...accent.split(' ').map((w) => ({ w, a: true }))];
  return (
    <motion.div className={`sec-head ${className}`} initial="hidden" whileInView="shown" viewport={{ once: true, margin: '0px 0px -12% 0px' }}>
      <motion.span className="sec-index" variants={{ hidden: { opacity: 0, y: 10 }, shown: { opacity: 1, y: 0, transition: { duration: 0.6, ease } } }}>
        {index}
      </motion.span>
      <h2 id={id}>
        {words.map(({ w, a }, i) => (
          <Fragment key={i}>
            <span className="word-mask">
              <motion.span className={`word${a ? ' serif' : ''}`}
                variants={{ hidden: { y: '110%' }, shown: { y: '0%', transition: { duration: 0.9, delay: 0.05 + i * 0.045, ease } } }}>
                {w}
              </motion.span>
            </span>{i < words.length - 1 ? ' ' : ''}
          </Fragment>
        ))}
      </h2>
      {children && (
        <motion.p variants={{ hidden: { opacity: 0, y: 16 }, shown: { opacity: 1, y: 0, transition: { duration: 0.8, delay: 0.25, ease } } }}>
          {children}
        </motion.p>
      )}
    </motion.div>
  );
}
