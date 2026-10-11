/** The five kinds of information, in the order the chart draws them. */
export type LayerKey = 'air' | 'water' | 'chlorine' | 'model' | 'human';

export const LAYERS: { key: LayerKey; title: string; style: string; source: string; can: string; cannot: string }[] = [
  { key: 'air', title: 'Weather forecast', style: 'Dotted, outside the tank',
    source: 'A public weather forecast for the campus location.', can: 'Whether hot days are coming, as context.', cannot: 'Stand in for tank-water temperature.' },
  { key: 'water', title: 'Measured tank-water temperature', style: 'Solid line, real readings',
    source: 'Thermometer or in-tank probe, with time and method.', can: 'How warm the stored water was, at that point and time.', cannot: 'Say whether the water is safe to drink.' },
  { key: 'chlorine', title: 'Recorded free chlorine', style: 'Separate lane, single readings',
    source: 'DPD strip, comparator or meter, optionally with a photo.', can: 'The disinfectant residual at one moment and point.', cannot: 'Prove potability or describe the whole tank.' },
  { key: 'model', title: 'Model estimate', style: 'Dashed with a band, only when validated',
    source: "A heat-balance model fitted to this tank's own readings.", can: 'An estimate with an error band, only after held-out validation.', cannot: 'Be shown beyond the horizon it was validated for.' },
  { key: 'human', title: 'Human decisions', style: 'Named, timed, with a reason',
    source: 'Wardens and technicians, by name.', can: 'Who accepted, rejected or resolved what, when and why.', cannot: 'Independently verify the physical work.' },
];
