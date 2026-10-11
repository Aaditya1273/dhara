import { useState } from 'react';
import { useMotionValueEvent, useScroll } from 'motion/react';
import { data } from '../data';
import { Logo } from './Icons';
import './Header.css';

const LINKS = [
  ['#workflow', 'How it works'],
  ['#priority', 'Testing priority'],
  ['#evidence', 'Evidence'],
  ['#trust', 'Trust'],
] as const;

/** Transparent over the hero; becomes a floating pill as soon as the page scrolls. */
export function Header() {
  const { scrollY } = useScroll();
  const [floating, setFloating] = useState(() => window.scrollY > 8);
  useMotionValueEvent(scrollY, 'change', (y) => setFloating(y > 8));

  return (
    <header className={`lp-header${floating ? ' is-floating' : ''}`}>
      <div className="lp-bar">
        <a className="brand" href={data.urls.home}><Logo /><span className="brand-word">DHARA</span></a>
        <nav className="lp-links" aria-label="Sections">
          {LINKS.map(([href, label]) => <a key={href} href={href}>{label}</a>)}
        </nav>
        <nav className="lp-account" aria-label="Account">
          {data.authenticated ? (
            <a className="btn btn-primary btn-sm" href={data.urls.dashboard}>Open dashboard</a>
          ) : (
            <>
              <a className="btn btn-ghost btn-sm" href={data.urls.login}>Sign in</a>
              <a className="btn btn-primary btn-sm" href={data.urls.register}>
                <span className="xs-hide">Register institution</span><span className="xs-show">Register</span>
              </a>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
