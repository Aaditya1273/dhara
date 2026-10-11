// Records the real DHARA app (local dev server) as high-DPI state screenshots plus the boxes of every
// element the cursor will interact with. The film compositor adds the cursor and camera moves.
const { chromium } = require('playwright-core');
const fs = require('fs');
const OUT = __dirname + '/cap/product/';
const BASE = 'http://localhost:8765';
const SLUG = 'demo-hostel-demonstration-data';
const EXE = process.env.HOME + '/.cache/ms-playwright/chromium_headless_shell-1247/chrome-headless-shell-linux64/chrome-headless-shell';
const PASS = 'demo-pass-2026'; // local seed_demo test password (local dev host only)
const meta = {};

async function shot(page, name, targets = {}, opts = {}) {
  await page.waitForTimeout(opts.wait ?? 350);
  const boxes = {};
  for (const [k, sel] of Object.entries(targets)) {
    const loc = typeof sel === 'string' ? page.locator(sel).first() : sel;
    const b = await loc.boundingBox().catch(() => null);
    if (b) boxes[k] = b;
  }
  await page.screenshot({ path: OUT + name + '.jpg', type: 'jpeg', quality: 92, fullPage: !!opts.full });
  const vp = page.viewportSize();
  meta[name] = { boxes, full: !!opts.full, vp, docH: await page.evaluate(() => document.documentElement.scrollHeight) };
  fs.writeFileSync(OUT + 'meta.json', JSON.stringify(meta, null, 1));
}

async function sel(page, name, value) {
  await page.evaluate(([n, v]) => { const e = document.querySelector(`select[name=${n}]`); if (!e) return; e.value = v; e.dispatchEvent(new Event('change', { bubbles: true })); }, [name, value]);
}

async function login(ctx, email) {
  const page = await ctx.newPage();
  await page.goto(BASE + '/login/');
  await page.fill('input[name=username]', email);
  await page.fill('input[name=password]', PASS);
  await Promise.all([page.waitForNavigation(), page.click('button[type=submit]')]);
  return page;
}

(async () => {
  const browser = await chromium.launch({ executablePath: EXE });
  const desk = { viewport: { width: 1280, height: 720 }, deviceScaleFactor: 2 };

  // ---- Technician: chlorine reading, then maintenance with photos ----
  const tctx = await browser.newContext(desk);
  const t = await login(tctx, 'technician@demo.dhara.test');
  await t.goto(`${BASE}/${SLUG}/tanks/1/`);
  await shot(t, 't1_tank', { record: 'a[href$="/measurements/new/"]' });
  await t.goto(`${BASE}/${SLUG}/tanks/1/measurements/new/`);
  await sel(t, 'kind', 'free_chlorine');
  await t.waitForTimeout(200);
  await sel(t, 'method', 'dpd_strip');
  await sel(t, 'entered_unit', 'mg/L');
  await shot(t, 't2_form0', { kind: 'select[name=kind]', value: 'input[name=entered_value]', submit: 'form button[type=submit]' });
  const v = '0.15';
  for (let i = 1; i <= v.length; i++) {
    await t.fill('input[name=entered_value]', v.slice(0, i));
    await shot(t, `t2_type${i}`, { value: 'input[name=entered_value]', submit: 'form button[type=submit]' }, { wait: 60 });
  }
  await Promise.all([t.waitForNavigation(), t.click('form button[type=submit]')]);
  await shot(t, 't3_after_measure', {}, { wait: 500 });
  // Maintenance with before/after photos.
  await t.goto(`${BASE}/${SLUG}/tanks/1/maintenance/new/`);
  await t.fill('input[name=provider_name]', 'Block A maintenance team').catch(() => {});
  await t.fill('textarea[name=notes]', 'Drained, scrubbed and refilled. Lid resealed.').catch(() => {});
  await t.setInputFiles('input[name=before_photos]', __dirname + '/../demo_files/DEMO-before.png').catch((e) => console.log('before', e.message));
  await t.setInputFiles('input[name=after_photos]', __dirname + '/../demo_files/DEMO-after.png').catch((e) => console.log('after', e.message));
  await t.waitForTimeout(600);
  await shot(t, 't4_maint_form', { submit: 'form button[type=submit]', before: 'input[name=before_photos]', after: 'input[name=after_photos]' }, { full: true });

  // ---- Warden: dashboard, priority, review, public page ----
  const wctx = await browser.newContext(desk);
  const w = await login(wctx, 'warden@demo.dhara.test');
  await w.goto(`${BASE}/${SLUG}/dashboard/`);
  await shot(w, 'w1_dashboard', { priority: 'a[href$="/test-priority/"]', review: 'a[href$="/review/"]' }, { full: true });
  await w.goto(`${BASE}/${SLUG}/test-priority/`);
  await shot(w, 'w2_priority', {}, { full: true, wait: 600 });
  await w.goto(`${BASE}/${SLUG}/tanks/1/`);
  await shot(w, 'w3_tank', {}, { full: true });
  await w.goto(`${BASE}/${SLUG}/review/`);
  await shot(w, 'w35_queue', { first: 'main a[href*="/maintenance/"]' }, { full: true });
  const eventUrl = BASE + await w.evaluate(() => [...document.querySelectorAll('main a[href*="/maintenance/"]')].map((a) => a.getAttribute('href')).find((h) => /maintenance\/\d+\/$/.test(h)));
  await w.goto(eventUrl);
  await shot(w, 'w4_event', { accept: 'input[name=decision][value=accepted]', notes: 'textarea[name=notes]', submit: 'form button[type=submit]', digest: 'text=/[0-9a-f]{16}/' }, { full: true });
  try {
  await w.check('input[name=decision][value=accepted]').catch(() => {});
  const note = 'Photos match Tank A. Accepted.';
  for (let i = 4; i <= note.length; i += 4) {
    await w.fill('textarea[name=notes]', note.slice(0, i));
    if (i % 8 === 0 || i + 4 > note.length) await shot(w, `w5_note${String(i).padStart(2, '0')}`, { notes: 'textarea[name=notes]', submit: 'form button[type=submit]' }, { wait: 40, full: true });
  }
  await w.fill('textarea[name=notes]', note);
  await shot(w, 'w5_notefull', { notes: 'textarea[name=notes]', submit: 'form button[type=submit]' }, { wait: 40, full: true });
  await Promise.all([w.waitForNavigation(), w.click('form button[type=submit]')]);
  await shot(w, 'w6_accepted', {}, { wait: 600, full: true });
  } catch (e) { console.log('review skipped:', e.message.split('\n')[0]); }
  // Public QR page on a phone.
  await w.goto(`${BASE}/${SLUG}/tanks/1/`);
  const tokenHref = await w.evaluate(() => [...document.querySelectorAll('a[href*="/qr/"]')].map((a) => a.getAttribute('href'))[0]);
  const pctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, isMobile: true });
  const p = await pctx.newPage();
  await p.goto(BASE + (tokenHref || '/'));
  await shot(p, 'p1_public', {}, { full: true, wait: 800 });
  console.log('done', Object.keys(meta).length, 'states; event', eventUrl, 'qr', tokenHref);
  await browser.close();
})().catch((e) => { console.error('FAILED', e); process.exit(1); });
