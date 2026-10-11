import { motion } from 'motion/react';
import { Badge } from '../../components/Badge';
import { Calendar, Camera, Check, Doc, Drop, QrGlyph, Signal, Thermo, User } from '../../components/Icons';

/* Simplified example screens, one per workflow step. Values are examples; the stage is labelled as such. */
const rise = (i: number) => ({ initial: { opacity: 0, y: 14 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.5, delay: 0.12 + i * 0.1, ease: [0.16, 1, 0.3, 1] as const } });

function Measure() {
  return (
    <div className="scr">
      <p className="scr-kicker">TANK-A · New measurement</p>
      <motion.div className="scr-row big" {...rise(0)}><span className="ico chlorine"><Drop /></span><div><small>Free chlorine</small><b>0.30 mg/L</b></div><span className="pill">DPD strip</span></motion.div>
      <motion.div className="scr-row" {...rise(1)}><span className="ico water"><Thermo /></span><div><small>Tank-water temperature</small><b>31.4 °C</b></div><span className="pill">probe</span></motion.div>
      <motion.div className="scr-probe" {...rise(2)}>
        <span className="probe-ico"><Signal /></span>
        <span className="probe-waves" aria-hidden="true"><i /><i /><i /></span>
        <span>In-tank probe → AWS IoT Core<small>reading, method, source and time kept</small></span>
      </motion.div>
    </div>
  );
}

function Prioritise() {
  const rules = ['Chlorine reading is 30 h old in heat', 'Forecast max 41 °C (air)', 'Rooftop tank, full sun'];
  return (
    <div className="scr">
      <p className="scr-kicker">Testing priority</p>
      <motion.div className="scr-verdict" {...rise(0)}><Badge tone="warn">High</Badge><b>Repeat measurement</b></motion.div>
      <ul className="scr-rules">
        {rules.map((r, i) => <motion.li key={r} {...rise(i + 1)}><span className="tick"><Check /></span>{r}</motion.li>)}
      </ul>
    </div>
  );
}

function Record() {
  return (
    <div className="scr">
      <p className="scr-kicker">Maintenance · Tank cleaning</p>
      <div className="scr-photos">
        <motion.div className="photo before" {...rise(0)}><Camera /><span>Before</span></motion.div>
        <motion.div className="photo after" {...rise(1)}><Camera /><span>After</span></motion.div>
        <motion.div className="photo doc" {...rise(2)}><Doc /><span>Invoice.pdf</span></motion.div>
      </div>
      <motion.div className="scr-hash" {...rise(3)}>
        <small>SHA-256 (example)</small>
        <code><motion.span initial={{ width: 0 }} animate={{ width: '100%' }} transition={{ duration: 1.4, delay: 0.6, ease: 'linear' }}>9f2c 41ab e07d 3c5e 88a1 0b6f d2e4 7c19</motion.span></code>
      </motion.div>
    </div>
  );
}

function Review() {
  return (
    <div className="scr">
      <p className="scr-kicker">Review queue</p>
      <motion.div className="scr-event" {...rise(0)}>
        <div><b>Tank cleaning, Block A</b><small>Submitted by a technician · 3 files</small></div>
        <Badge tone="info">Pending review</Badge>
      </motion.div>
      <motion.div className="scr-actions" {...rise(1)}>
        <motion.span className="act accept" initial={{ scale: 1 }} animate={{ scale: [1, 0.94, 1] }} transition={{ delay: 1, duration: 0.35 }}><Check /> Accept</motion.span>
        <span className="act">Ask for more</span><span className="act">Reject</span>
      </motion.div>
      <motion.div className="scr-stamp" initial={{ opacity: 0, scale: 1.6, rotate: -12 }} animate={{ opacity: 1, scale: 1, rotate: -6 }}
        transition={{ type: 'spring', stiffness: 320, damping: 16, delay: 1.25 }}>Accepted · with a reason</motion.div>
      <motion.p className="scr-note" {...rise(2)}><User /> The reviewer is never the person who submitted.</motion.p>
    </div>
  );
}

function FollowUp() {
  return (
    <div className="scr">
      <p className="scr-kicker">Follow-ups</p>
      <motion.div className="scr-task" {...rise(0)}>
        <div className="task-top"><b>Repeat the chlorine measurement</b><Badge tone="warn">Open</Badge></div>
        <div className="task-meta"><span><User /> Responsible person</span><span><Calendar /> Due in 3 days</span></div>
        <div className="task-bar"><motion.i initial={{ width: 0 }} animate={{ width: '35%' }} transition={{ duration: 1, delay: 0.5 }} /></div>
      </motion.div>
      <motion.div className="scr-task faint" {...rise(1)}>
        <div className="task-top"><b>Upload the laboratory report</b><Badge tone="warn">Open</Badge></div>
        <div className="task-meta"><span><Calendar /> Due tomorrow</span></div>
      </motion.div>
    </div>
  );
}

function Verify() {
  return (
    <div className="scr qr">
      <motion.div className="qr-phone" {...rise(0)}>
        <div className="qr-head"><span className="qr-g"><QrGlyph /></span><div><b>TANK-A</b><small>Public tank record</small></div></div>
        <div className="qr-line"><small>Last free chlorine</small><b>0.45 mg/L</b></div>
        <div className="qr-line"><small>Follow-up</small><Badge tone="good">Resolved</Badge></div>
        <div className="qr-line"><small>Closed with</small><b>notes and a name</b></div>
        <p className="qr-foot">Not a certificate that water is safe to drink.</p>
      </motion.div>
    </div>
  );
}

export const SCREENS = [Measure, Prioritise, Record, Review, FollowUp, Verify];
