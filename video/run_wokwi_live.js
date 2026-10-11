const { chromium } = require('playwright-core');
const fs = require('fs');
const fn = eval(fs.readFileSync('/home/bajrangi/Wins/dhara/.playwright-mcp/wokwi-live.js', 'utf8'));
(async () => {
  const b = await chromium.launch({ executablePath: process.env.HOME + '/.cache/ms-playwright/chromium_headless_shell-1247/chrome-headless-shell-linux64/chrome-headless-shell' });
  const page = await (await b.newContext({ viewport: { width: 1920, height: 1080 } })).newPage();
  page.on('dialog', (d) => d.accept().catch(() => {}));
  const r = await fn(page); console.log(JSON.stringify(r)); await b.close();
})().catch((e) => { console.error('FAILED', e.message); process.exit(1); });
