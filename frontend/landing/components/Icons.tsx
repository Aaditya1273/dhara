/* Small inline icons. Decorative unless a label is passed by the caller. */
type P = { className?: string };
const svg = { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, 'aria-hidden': true };

export const Logo = () => (
  <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden="true" focusable="false">
    <path d="M16 3.5c0 0-8.5 9.6-8.5 15.6a8.5 8.5 0 0 0 17 0C24.5 13.1 16 3.5 16 3.5z" fill="#0866f5" />
    <path d="M11.2 19.6c1.6-1.3 3.2-1.3 4.8 0s3.2 1.3 4.8 0" fill="none" stroke="#ffffff" strokeWidth="1.7" strokeLinecap="round" />
    <path d="M11.2 23.2c1.6-1.3 3.2-1.3 4.8 0s3.2 1.3 4.8 0" fill="none" stroke="#ffffff" strokeWidth="1.7" strokeLinecap="round" opacity=".55" />
  </svg>
);
export const Thermo = ({ className }: P) => <svg {...svg} className={className}><path d="M12 3v11.2a3.5 3.5 0 1 0 2 0V3a1 1 0 0 0-2 0z" /><path d="M8 7h2M8 10h2" /></svg>;
export const Sun = ({ className }: P) => <svg {...svg} className={className}><circle cx="12" cy="12" r="4" /><path d="M12 2.5V5M12 19v2.5M2.5 12H5M19 12h2.5M5.3 5.3l1.8 1.8M16.9 16.9l1.8 1.8M5.3 18.7l1.8-1.8M16.9 7.1l1.8-1.8" /></svg>;
export const Drop = ({ className }: P) => <svg {...svg} className={className}><path d="M12 3s-6 7-6 11a6 6 0 0 0 12 0c0-4-6-11-6-11z" /></svg>;
export const Alert = ({ className }: P) => <svg {...svg} className={className}><path d="M12 4 2.8 20h18.4zM12 10v4.5M12 17.2v.1" /></svg>;
export const Check = ({ className }: P) => <svg {...svg} className={className} strokeWidth={2.4}><path d="m5 12.5 4.2 4.2L19 7" /></svg>;
export const Camera = ({ className }: P) => <svg {...svg} className={className}><path d="M4 8h3l1.5-2h7L17 8h3v11H4z" /><circle cx="12" cy="13.5" r="3.2" /></svg>;
export const Doc = ({ className }: P) => <svg {...svg} className={className}><path d="M7 3h7l4 4v14H7zM14 3v4h4M10 12h5M10 16h5" /></svg>;
export const Calendar = ({ className }: P) => <svg {...svg} className={className}><rect x="4" y="5" width="16" height="15" rx="2" /><path d="M4 10h16M9 3v4M15 3v4" /></svg>;
export const Signal = ({ className }: P) => <svg {...svg} className={className}><path d="M5 12a7 7 0 0 1 14 0M8 12a4 4 0 0 1 8 0" /><circle cx="12" cy="12" r="1.2" fill="currentColor" /><path d="M12 13v7" /></svg>;
export const User = ({ className }: P) => <svg {...svg} className={className}><circle cx="12" cy="8" r="3.5" /><path d="M5 20c1.2-3.5 4-5 7-5s5.8 1.5 7 5" /></svg>;
export const Pause = ({ className }: P) => <svg {...svg} className={className}><path d="M9 6v12M15 6v12" strokeWidth={2.4} /></svg>;
export const Play = ({ className }: P) => <svg {...svg} className={className}><path d="M8 5.5v13l10-6.5z" fill="currentColor" /></svg>;
export const QrGlyph = ({ className }: P) => (
  <svg className={className} viewBox="0 0 21 21" aria-hidden="true">
    <path d="M1 1h7v7H1z M13 1h7v7h-7z M1 13h7v7H1z" fill="none" stroke="currentColor" strokeWidth="2" />
    <path d="M3.5 3.5h2v2h-2z M15.5 3.5h2v2h-2z M3.5 15.5h2v2h-2z M11 11h2v2h-2z M15 13h2v2h-2z M13 17h2v2h-2z M18 17h2v3h-2z M11 15h2v2h-2z" fill="currentColor" />
  </svg>
);
