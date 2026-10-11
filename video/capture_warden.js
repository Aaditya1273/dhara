const { chromium } = require('playwright-core');
const fs = require('fs');
const OUT = __dirname + '/cap/product/', BASE = 'http://localhost:8765', SLUG = 'demo-hostel-demonstration-data';
const EXE = process.env.HOME + '/.cache/ms-playwright/chromium_headless_shell-1247/chrome-headless-shell-linux64/chrome-headless-shell';
const meta = JSON.parse(fs.readFileSync(OUT + 'meta.json'));
async function shot(page, name, targets = {}, full = true) {
  await page.waitForTimeout(500);
  const boxes = {};
  for (const [k, sel] of Object.entries(targets)) { const b = await page.locator(sel).first().boundingBox().catch(() => null); if (b) boxes[k] = b; }
  await page.screenshot({ path: OUT + name + '.jpg', type: 'jpeg', quality: 92, fullPage: full });
  meta[name] = { boxes, full, vp: page.viewportSize(), docH: await page.evaluate(() => document.documentElement.scrollHeight) };
  fs.writeFileSync(OUT + 'meta.json', JSON.stringify(meta, null, 1));
}
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const ctx = await b.newContext({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 2 });
  const w = await ctx.newPage();
  await w.goto(BASE + '/login/'); await w.fill('input[name=username]', 'warden@demo.dhara.test'); await w.fill('input[name=password]', 'demo-pass-2026');
  await Promise.all([w.waitForNavigation(), w.click('button[type=submit]')]);
  await w.goto(`${BASE}/${SLUG}/dashboard/`); await shot(w, 'w1_dashboard', { priority: 'a[href$="/test-priority/"]' });
  await w.goto(`${BASE}/${SLUG}/test-priority/`); await shot(w, 'w2_priority', {});
  await w.goto(`${BASE}/${SLUG}/tanks/1/`); await shot(w, 'w3_tank', {});
  const p = await (await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, isMobile: true })).newPage();
  await p.goto(BASE + '/qr/993xAmrTr7ukV8BTBQV_T_Dk/'); await shot(p, 'p1_public', {});
  await b.close(); console.log('ok');
})().catch((e) => { console.error('FAILED', e.message); process.exit(1); });
