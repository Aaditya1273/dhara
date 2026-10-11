import type { ReactNode } from 'react';
import type { Tone } from '../types';

/** Same markup as the Django {% badge %} tag, so colours and shapes come from the shared stylesheet. */
export const Badge = ({ tone, children }: { tone: Tone; children: ReactNode }) => <span className={`badge badge-${tone}`}>{children}</span>;
