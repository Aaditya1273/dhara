// Exact element boxes (CSS px, document coordinates) on the same pages and viewport as the screenshots.
const { chromium } = require('playwright-core');
const fs = require('fs');
const BASE = 'http://localhost:8765', S = '/demo-hostel-demonstration-data';
const EXE = process.env.HOME + '/.cache/ms-playwright/chromium_headless_shell-1247/chrome-headless-shell-linux64/chrome-headless-shell';
const probe = (specs) => specs.map(([key, text, mode]) => {
  const all = [...document.querySelectorAll('body *')].filter((e) => e.children.length === 0 || [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()));
  let el = all.find((e) => e.textContent.includes(text) && e.offsetParent !== null);
  if (!el) return [key, null];
  if (mode === 'card') {
    let p = el;
    while (p && p !== document.body) { const cs = getComputedStyle(p); if (parseFloat(cs.borderTopLeftRadius) >= 10 && (cs.boxShadow !== 'none' || cs.borderTopWidth !== '0px') && p.getBoundingClientRect().width > 300) break; p = p.parentElement; }
    el = p;
  } else if (mode === 'block') { el = el.closest('p, li, div') || el; }
  const r = el.getBoundingClientRect();
  return [key, [Math.round(r.x), Math.round(r.y + scrollY), Math.round(r.width), Math.round(r.height)]];
});
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const login = async (email) => { const p = await (await b.newContext({ viewport: { width: 1280, height: 720 } })).newPage(); await p.goto(BASE + '/login/'); await p.fill('input[name=username]', email); await p.fill('input[name=password]', 'demo-pass-2026'); await Promise.all([p.waitForNavigation(), p.click('button[type=submit]')]); return p; };
  const w = await login('warden@demo.dhara.test'), out = {};
  const at = async (page, url, specs) => { await page.goto(BASE + url); await page.waitForTimeout(300); return Object.fromEntries(await page.evaluate(probe, specs)); };
  out.w2_priority = await at(w, S + '/test-priority/', [['tankA', 'Tank A · overhead tank', 'card'], ['why', 'is below the configured minimum', 'block'], ['urgent', 'Warden review', 'text']]);
  out.w3_tank = await at(w, S + '/tanks/1/', [['chlorine', 'Latest free chlorine', 'card'], ['qr', 'QR status page', 'card']]);
  out.w35_queue = await at(w, S + '/review/', [['rule', 'You cannot review your own', 'block']]);
  const href = await w.evaluate(() => [...document.querySelectorAll('main a[href*="/maintenance/"]')].map((a) => a.getAttribute('href')).find((h) => /maintenance\/\d+\/$/.test(h)));
  out.w4_event = await at(w, href, [['sha', 'SHA-256', 'block'], ['evidence', 'Evidence', 'card']]);
  const t = await login('technician@demo.dhara.test');
  out.t2_form0 = await at(t, S + '/tanks/1/measurements/new/', [['reading', 'Reading', 'text'], ['form', 'Measurement', 'card']]);
  const inp = await t.locator('input[name=entered_value]').boundingBox(); out.t2_form0.input = [inp.x, inp.y, inp.width, inp.height].map(Math.round);
  fs.writeFileSync(__dirname + '/cap/boxes.json', JSON.stringify(out, null, 1)); console.log(JSON.stringify(out));
  await b.close();
})();
