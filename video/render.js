// Renders film.html frame by frame (seek(t)) and pipes JPEG frames into ffmpeg.
const { chromium } = require('playwright-core');
const { spawn } = require('child_process');
const EXE = process.env.HOME + '/.cache/ms-playwright/chromium_headless_shell-1247/chrome-headless-shell-linux64/chrome-headless-shell';
const [, , mode, a, b, out] = process.argv; // mode: stills|range
const FPS = 30;
(async () => {
  const browser = await chromium.launch({ executablePath: EXE, args: ['--allow-file-access-from-files', '--disable-web-security'] });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  page.on('pageerror', (e) => console.error('PAGEERR', e.message));
  await page.goto('file://' + __dirname + '/film.html');
  await page.evaluate(() => window.ready);
  const cdp = await page.context().newCDPSession(page);
  const grab = async (t) => { await page.evaluate((t) => window.seek(t), t); const r = await cdp.send('Page.captureScreenshot', { format: 'jpeg', quality: 93, optimizeForSpeed: true }); return Buffer.from(r.data, 'base64'); };
  if (mode === 'stills') {
    for (const t of a.split(',').map(Number)) require("fs").writeFileSync(`${b}/still_${t.toFixed(1)}.jpg`, await grab(t));
  } else {
    const f0 = Math.round(+a * FPS), f1 = Math.round(+b * FPS);
    const ff = spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf', '16', '-pix_fmt', 'yuv420p', out]);
    for (let f = f0; f < f1; f++) { const buf = await grab(f / FPS); if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r)); }
    ff.stdin.end(); await new Promise((r) => ff.on('close', r));
  }
  await browser.close();
})().catch((e) => { console.error('FAILED', e); process.exit(1); });
