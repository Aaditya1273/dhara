import { MotionConfig } from 'motion/react';
import { Header } from './components/Header';
import { Hero } from './sections/Hero/Hero';
import { Problem } from './sections/Problem/Problem';
import { Layers } from './sections/Layers/Layers';
import { Priority } from './sections/Priority/Priority';
import { Lanes } from './sections/Lanes/Lanes';
import { Workflow } from './sections/Workflow/Workflow';
import { Trust } from './sections/Trust/Trust';
import { Closing } from './sections/Closing/Closing';

/* reducedMotion="user": Motion drops transform animations for people who ask for less motion.
   Scroll-linked effects check the same preference through useMotionOK(). */
export function App() {
  return (
    <MotionConfig reducedMotion="user">
      <Header />
      <Hero />
      <Problem />
      <Layers />
      <Priority />
      <Lanes />
      <Workflow />
      <Trust />
      <Closing />
    </MotionConfig>
  );
}
