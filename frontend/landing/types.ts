/** Shape of the JSON that Django renders into #landing-data (see LandingPageView). */
export type Tone = 'good' | 'warn' | 'bad' | 'info' | 'neutral';
export type Level = 'urgent' | 'high' | 'medium' | 'low' | 'none';

export interface Scenario {
  key: string;
  title: string;
  evidence: [string, string][];
  level: Level;
  levelLabel: string;
  levelTone: Tone;
  actionLabel: string;
  actionable: boolean;
  reasons: string[];
  context: string[];
  due: string | null;
  inputs: {
    chlorine: number | null;
    chlorineAgeH: number | null;
    waterC: number | null;
    waterAgeH: number | null;
    airMaxC: number;
  };
}

export interface LandingData {
  authenticated: boolean;
  urls: { home: string; register: string; login: string; dashboard: string };
  demoQrUrl: string | null;
  img: { hero1672: string; hero1100: string; heroMobile: string };
  cfg: { chlorineMin: number; chlorineMaxAgeH: number; warmC: number; hotC: number };
  scenarios: Scenario[];
}
