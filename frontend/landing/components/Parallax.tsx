import { useRef, type ReactNode } from 'react';
import { motion, useScroll, useTransform } from 'motion/react';
import { useMotionOK } from '../hooks/media';

/** Moves its content at a different rate from the page while it crosses the viewport. speed 0.2 ≈ ±80px of travel. */
export function Parallax({ children, speed = 0.15, className }: { children: ReactNode; speed?: number; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const ok = useMotionOK();
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start end', 'end start'] });
  const y = useTransform(scrollYProgress, [0, 1], [speed * 400, -speed * 400]);
  return <motion.div ref={ref} className={className} style={ok ? { y } : undefined}>{children}</motion.div>;
}
