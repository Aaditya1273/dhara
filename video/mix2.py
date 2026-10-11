import json, numpy as np, soundfile as sf, subprocess
from scipy.signal import resample_poly
SR = 48000; TL = json.load(open('timeline.json')); DUR = TL['total']; N = int(SR * DUR)
Ls = lambda n: TL['lines'][str(n)][0]; Ld = lambda n: TL['lines'][str(n)][1]; S = TL['scenes']
def load(path):
    if path.endswith('.mp3'):
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'f32le', '-ac', '2', '-ar', str(SR), '-'], capture_output=True).stdout
        return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()
    x, sr = sf.read(path, dtype='float32', always_2d=True)
    if sr != SR: x = resample_poly(x, SR, sr, axis=0).astype(np.float32)
    return np.repeat(x, 2, axis=1) if x.shape[1] == 1 else x
def place(buf, x, t, gain=1.0):
    i = int(t * SR); j = min(N, i + len(x))
    if 0 <= i < N: buf[i:j] += x[:j - i] * gain
vo = np.zeros((N, 2), np.float32); sfx = np.zeros((N, 2), np.float32)
for n in range(1, 17): place(vo, load(f'audio/fast/vo_L{n:02d}.wav'), Ls(n))
X = {n: load(f'audio/sfx_{n}.wav') for n in ['whoosh', 'whoosh_rev', 'impact', 'riser', 'drop', 'ripple', 'click', 'type', 'ping']}
def rm(o, pairs):  # old scene-local time -> new absolute (piecewise linear), pairs [[newLocalAbs, old], ...]
    for i in range(1, len(pairs)):
        if o <= pairs[i][1]: (a0, b0), (a1, b1) = pairs[i - 1], pairs[i]; return a0 + (o - b0) / (b1 - b0) * (a1 - a0)
    a, b = pairs[-1]; return a + (o - b)
k6 = Ld(6) / 17.2; arch = lambda o: Ls(6) + (o - 0.6) * k6
proof = lambda o: rm(o, [[Ls(7), 0.6], [Ls(7) + Ld(7), 12.36], [Ls(8), 13.0], [Ls(8) + Ld(8), 24.1]])
imp = lambda o: rm(o, [[Ls(14), 0.8], [Ls(14) + Ld(14), 6.8], [Ls(15), 7.4], [Ls(15) + Ld(15), 14.56]])
a10, a11, a13 = Ls(10), Ls(11), Ls(13)
ev = [('whoosh_rev', 0.0, .5), ('impact', 1.97, .9), ('whoosh', S[1][0] - 0.45, .7),
      ('impact', Ls(2) + Ld(2) - 0.85, .8)] + [('ping', Ls(3) + Ld(3) * f, .35) for f in (0, .26, .5, .73)] + [
      ('whoosh', S[2][0] - 0.3, .7), ('impact', S[2][0] + 0.1, .9)] + [('ping', Ls(5) + Ld(5) * f, .3) for f in (.02, .36, .66)] + [
      ('whoosh', S[3][0] - 0.3, .6), ('ping', arch(3.6), .3), ('ping', arch(9.2), .3), ('ping', arch(11.0), .3),
      ('whoosh', S[4][0] - 0.3, .6), ('whoosh_rev', proof(10.0) - 1.0, .55), ('impact', proof(11.0), .9), ('ping', proof(22.5), .4),
      ('whoosh', S[5][0] - 0.3, .6), ('click', a10 + 0.55, .9), ('click', a11 + 0.62, .9), ('whoosh', a13 - 0.15, .5),
      ('whoosh', S[6][0] - 0.3, .6), ('impact', imp(8.4), .8), ('whoosh', S[7][0] - 0.3, .6), ('impact', S[7][0] + 0.1, .7)]
for n, t, gn in ev: place(sfx, X[n], t, gn)
for o, dur in [(11.6, 1.2), (14.2, 1.0), (17.0, 1.0)]:
    t0 = proof(o)
    for k in range(int(dur / 0.06)): place(sfx, X['type'], t0 + k * 0.06 + (k % 3) * 0.007, .42)
for k in range(4): place(sfx, X['type'], a11 + 0.9 + k * 0.13, .6)
# music: start on the drop, then a downbeat-aligned crossfade back into the high-energy section before the track's ending
tr = load('audio/music.mp3'); A0, CUT, B0, XF = 73.0, 185.13, 138.62, 0.35
p1 = tr[int(A0 * SR):int((CUT + XF) * SR)]; p2 = tr[int(B0 * SR):]
x = int(XF * SR); fo = np.cos(np.linspace(0, np.pi / 2, x))[:, None]; fi = np.sin(np.linspace(0, np.pi / 2, x))[:, None]
music = np.concatenate([p1[:-x], p1[-x:] * fo + p2[:x] * fi, p2[x:]])[:N]
if len(music) < N: music = np.pad(music, ((0, N - len(music)), (0, 0)))
env = np.abs(vo).max(axis=1); w = int(0.05 * SR); env = np.convolve(env, np.ones(w) / w, 'same'); duck = np.clip(env / 0.05, 0, 1)
gg = np.empty_like(duck); a, r = np.exp(-1 / (0.03 * SR)), np.exp(-1 / (0.4 * SR)); y = 0.0
for i in range(0, len(duck), 64): tg = duck[i:i + 64].max(); c = a if tg > y else r; y = tg + (y - tg) * (c ** 64); gg[i:i + 64] = y
mg = 0.7 * (1 - 0.5 * gg); tt = np.arange(N) / SR; mg *= np.clip((DUR - 0.3 - tt) / 3.5, 0, 1)
mix = music * mg[:, None] + vo + sfx * 0.55; mix /= max(1e-6, np.abs(mix).max()) / 0.89
sf.write('out/mix2.wav', mix, SR, subtype='PCM_24'); print('mix2 ok', round(N / SR, 2), 's; crossfade at film', round(CUT - A0, 2), 's')
