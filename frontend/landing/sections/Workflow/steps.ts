import type { Tone } from '../../types';

export interface Step { title: string; short: string; text: string; keeps: { badges: [Tone, string][]; note: string } }

export const STEPS: Step[] = [
  { title: 'Measure', short: 'Measure',
    text: 'A technician records tank-water temperature or free chlorine from a phone, or an in-tank probe sends readings through AWS IoT Core.',
    keeps: { badges: [['info', 'probe']], note: 'reading, method, source and time' } },
  { title: 'Prioritise', short: 'Prioritise',
    text: 'Rules compare reading age and values with your thresholds and the weather forecast, and explain every reason.',
    keeps: { badges: [['warn', 'High']], note: 'with the rules that fired' } },
  { title: 'Record evidence', short: 'Record',
    text: 'Maintenance is submitted with before-and-after photos and documents. Files are validated on the server and fingerprinted.',
    keeps: { badges: [['good', 'Evidence attached']], note: 'with SHA-256 digests' } },
  { title: 'Review', short: 'Review',
    text: 'A warden who did not submit the work accepts it, rejects it or asks for more evidence, with a reason.',
    keeps: { badges: [['info', 'Pending review'], ['good', 'Accepted']], note: '' } },
  { title: 'Follow up', short: 'Follow up',
    text: 'Unmet schedules, missing reports and reviewer requests open follow-ups for the responsible person.',
    keeps: { badges: [['warn', 'Open']], note: 'assigned, with a due date' } },
  { title: 'Verify resolution', short: 'Verify',
    text: 'A task closes only when someone records what was done. The public QR page shows the outcome without private details.',
    keeps: { badges: [['good', 'Resolved']], note: 'with notes and a name' } },
];
