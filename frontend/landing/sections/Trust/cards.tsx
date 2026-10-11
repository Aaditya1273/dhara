import type { ReactNode } from 'react';
import { User } from '../../components/Icons';

/* Each card leads with a visual and keeps the exact statements. */
export interface TrustCard { key: string; title: string; items: string[]; visual: ReactNode; tone?: 'not' }

export const CARDS: TrustCard[] = [
  { key: 'recorded', title: 'Recorded', items: ['What was measured, and the method', 'When it was measured and when entered', 'Who submitted it, or which probe', 'Which lab documents exist'],
    visual: (
      <div className="tv-ledger">
        {[['08:10', 'Free chlorine', '0.30 mg/L'], ['14:20', 'Tank water', '31.4 °C'], ['16:02', 'Lab report', 'PDF']].map(([t, k, v]) => (
          <div key={t}><span>{t}</span><b>{k}</b><i>{v}</i></div>
        ))}
      </div>
    ) },
  { key: 'reviewed', title: 'Reviewed by', items: ['Wardens of that institution only', 'Never the person who submitted', 'With a reason for rejections', 'Roles that apply per institution'],
    visual: (
      <div className="tv-people">
        <span className="who"><User /><small>Submitter</small></span>
        <span className="neq">≠</span>
        <span className="who warden"><User /><small>Warden</small></span>
      </div>
    ) },
  { key: 'traceable', title: 'Traceable', items: ['SHA-256 for every evidence file', 'Re-check a digest at any time', 'Corrections as new events', 'An activity log of every action'],
    visual: (
      <div className="tv-hash"><small>sha256 (example)</small><code>9f2c41ab e07d3c5e<br />88a10b6f d2e47c19</code></div>
    ) },
  { key: 'not', title: 'Not claimed', tone: 'not', items: ['That water is safe to drink', 'That a photo is genuine', 'That a forecast is a measurement', 'That the log is tamper-proof'],
    visual: <div className="tv-stamp"><span>Safe to drink</span></div> },
];

export const STATEMENTS = CARDS.flatMap((c) => c.items.map((t) => ({ t, not: c.tone === 'not' })));
