import type { LandingData } from './types';

/** Server data: real rule-engine output for the example situations, configured thresholds and URLs. */
export const data: LandingData = JSON.parse(document.getElementById('landing-data')?.textContent ?? '{}');
