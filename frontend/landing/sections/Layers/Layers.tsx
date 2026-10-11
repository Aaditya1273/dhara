import { useRef, useState } from 'react';
import { useMotionValueEvent, useScroll } from 'motion/react';
import { SectionHead } from '../../components/SectionHead';
import { Reveal } from '../../components/Reveal';
import { LayerChart } from './LayerChart';
import { LAYERS, type LayerKey } from './layers';
import './Layers.css';

/** One illustrated tank timeline. Scrolling draws the five layers one after another; choosing a layer isolates it
    and explains its source and limits. */
export function Layers() {
  const stageRef = useRef<HTMLDivElement>(null);
  const [focus, setFocus] = useState<LayerKey | null>(null);
  const [drawing, setDrawing] = useState(-1);
  const { scrollYProgress } = useScroll({ target: stageRef, offset: ['start 85%', 'center 45%'] });
  useMotionValueEvent(scrollYProgress, 'change', (p) => setDrawing(p >= 1 ? -1 : Math.min(4, Math.floor(p / 0.2))));
  const active = LAYERS.find((l) => l.key === focus);

  return (
    <section className="lp-section" aria-labelledby="layers-title">
      <div className="lp-wrap">
        <SectionHead id="layers-title" index="One tank. Five places to look." lead="Measured, recorded, forecast, estimated," accent="decided.">
          Each kind of information has its own source, its own drawing style and its own limits. DHARA never blends them into a single score.
        </SectionHead>
        <div className="layers">
          <div className="layer-list" role="group" aria-label="Show one kind of information">
            {LAYERS.map((l, i) => (
              <button key={l.key} type="button" aria-pressed={focus === l.key}
                className={`layer-btn${drawing === i ? ' is-drawing' : ''}`} onClick={() => setFocus(focus === l.key ? null : l.key)}>
                <i className={`swatch ${l.key}`} aria-hidden="true" />
                <span><strong>{l.title}</strong><span>{l.style}</span></span>
              </button>
            ))}
          </div>
          <Reveal className="layer-stage-wrap">
            <div ref={stageRef} className="layer-stage" data-focus={focus ?? undefined}>
              <div className="layer-stage-top">
                <strong>One tank over five days</strong>
                <span className="badge badge-neutral">Illustration, not measured data</span>
              </div>
              <LayerChart progress={scrollYProgress} />
              <div className="layer-explain" aria-live="polite">
                {active ? (
                  <><div><b>Source</b>{active.source}</div><div><b>Can tell you</b>{active.can}</div><div><b>Cannot</b>{active.cannot}</div></>
                ) : (
                  <div className="all"><b>Five kinds, five drawing styles</b>Move across the chart to read any moment, or choose a layer to see its source and limits. Solid means measured, dotted means forecast, dashed means estimated.</div>
                )}
              </div>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
