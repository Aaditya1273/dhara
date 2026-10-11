const { chromium } = require('playwright-core');
const fs = require('fs');
const OUT = __dirname + '/cap/p5/', BASE = 'http://localhost:8765', S = '/demo-hostel-demonstration-data';
const EXE = process.env.HOME + '/.cache/ms-playwright/chromium_headless_shell-1247/chrome-headless-shell-linux64/chrome-headless-shell';
const meta = {};
async function box(page, sel) { const l = page.locator(sel).first(); if (!(await l.count())) return null; const b = await l.boundingBox(); const sy = await page.evaluate(() => scrollY); return b && [b.x, b.y + sy, b.width, b.height].map(Math.round); }
async function shot(page, name, sels = {}) { await page.waitForTimeout(500); const boxes = {}; for (const [k, s] of Object.entries(sels)) boxes[k] = await box(page, s);
  await page.screenshot({ path: OUT + name + '.jpg', type: 'jpeg', quality: 92, fullPage: true }); meta[name] = { boxes, url: page.url().replace(BASE, '') }; fs.writeFileSync(OUT + 'meta.json', JSON.stringify(meta, null, 1)); }
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const ctx = await b.newContext({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 2 }), w = await ctx.newPage();
  await w.goto(BASE + '/login/'); await w.fill('input[name=username]', 'warden@demo.dhara.test'); await w.fill('input[name=password]', 'demo-pass-2026'); await Promise.all([w.waitForNavigation(), w.click('button[type=submit]')]);
  await w.goto(BASE + S + '/review/');
  await shot(w, 'queue', { ev3: 'a[href$="/maintenance/3/"]', rule: 'text=You cannot review your own' });
  await w.goto(BASE + S + '/maintenance/3/');
  await shot(w, 'event', { photo1: 'main img >> nth=0', photo2: 'main img >> nth=1', sha: 'text=/[0-9a-f]{64}/ >> nth=0', recheck: 'button:has-text("Re-check"), a:has-text("Re-check")', accept: 'input[name=decision][value=accepted]', notes: 'textarea[name=notes]', submit: 'form:has(textarea[name=notes]) button[type=submit]' });
  const rc = w.locator('button:has-text("Re-check"), a:has-text("Re-check")').first();
  if (await rc.count()) { await rc.click(); await w.waitForLoadState('load'); await shot(w, 'verified', { msg: '.messages, [role=status], .notice' }); await w.goto(BASE + S + '/maintenance/3/'); }
  if (await w.locator('input[name=decision][value=accepted]').count()) {
    await w.check('input[name=decision][value=accepted]'); await w.fill('textarea[name=notes]', 'Photos show Tank A opened, scrubbed and refilled. Accepted.');
    await shot(w, 'event_filled', { accept: 'input[name=decision][value=accepted]', notes: 'textarea[name=notes]', submit: 'form:has(textarea[name=notes]) button[type=submit]' });
    await Promise.all([w.waitForNavigation(), w.click('form:has(textarea[name=notes]) button[type=submit]')]);
    await shot(w, 'accepted', { badge: 'text=Accepted' });
  }
  await w.goto(BASE + S + '/follow-ups/'); await shot(w, 'followups', {});
  await w.goto(BASE + S + '/dashboard/'); await shot(w, 'dashboard', {});
  await w.goto(BASE + S + '/test-priority/'); await shot(w, 'priority', { tankA: 'li:has-text("Tank A · overhead tank")', why: 'text=is below the configured minimum' });
  console.log(JSON.stringify(meta)); await b.close();
})().catch((e) => { console.error('FAILED', e.message); process.exit(1); });
