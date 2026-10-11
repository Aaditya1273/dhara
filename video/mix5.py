import json, numpy as np, soundfile as sf, subprocess
from scipy.signal import resample_poly
SR = 48000; TL = json.load(open('timeline5.json')); DUR = TL['total']; N = int(SR * DUR)
S = lambda n: TL['lines'][str(n)][0]; D = lambda n: TL['lines'][str(n)][1]; SEC = TL['sections']
def load(p):
    if p.endswith('.mp3'):
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', p, '-f', 'f32le', '-ac', '2', '-ar', str(SR), '-'], capture_output=True).stdout
        return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()
    x, sr = sf.read(p, dtype='float32', always_2d=True)
    if sr != SR: x = resample_poly(x, SR, sr, axis=0).astype(np.float32)
    return np.repeat(x, 2, axis=1) if x.shape[1] == 1 else x
def place(b, x, t, gn=1.0):
    i = int(t * SR); j = min(N, i + len(x))
    if 0 <= i < N: b[i:j] += x[:j - i] * gn
vo = np.zeros((N, 2), np.float32); sfx = np.zeros((N, 2), np.float32)
for n in range(1, 25): place(vo, load(f'audio/v5/vo_{n:02d}.wav'), S(n))
X = lambda n: load(f'audio/sfx_{n}.wav')
for a, b in SEC[1:]: place(sfx, X('whoosh'), a - 0.35, .3)
clicks = [S(15) + 0.85, S(17) + D(17) * 0.62 - 0.15, S(18) + 0.9, S(18) + D(18) * 0.55 - 0.15]
for c in clicks: place(sfx, X('click'), c, .7)
for k in range(4): place(sfx, X('type'), S(15) + 1.2 + k * 0.11, .5)
for t in [S(5) + 0.3, S(6) + 0.4, S(23) + 0.4]: place(sfx, X('ping'), t, .25)
place(sfx, X('impact'), S(22) + 1.4, .5)
# music: start on the drop, loop the energetic section on downbeats (beat = 0.612 s, downbeats k = 2 mod 4)
tr = load('audio/music.mp3'); XF = 0.4
segs = [(73.0, 185.13)]; total = segs[0][1] - segs[0][0]
while total < DUR + 1: segs.append((138.62, 185.13)); total += 185.13 - 138.62
parts = [tr[int(a * SR):int((b + XF) * SR)] for a, b in segs]; x = int(XF * SR)
fo = np.cos(np.linspace(0, np.pi / 2, x))[:, None]; fi = np.sin(np.linspace(0, np.pi / 2, x))[:, None]
music = parts[0]
for p in parts[1:]: music = np.concatenate([music[:-x], music[-x:] * fo + p[:x] * fi, p[x:]])
music = music[:N]
env = np.abs(vo).max(axis=1); w = int(0.05 * SR); env = np.convolve(env, np.ones(w) / w, 'same'); duck = np.clip(env / 0.05, 0, 1)
gg = np.empty_like(duck); a_, r_ = np.exp(-1 / (0.03 * SR)), np.exp(-1 / (0.45 * SR)); y = 0.0
for i in range(0, len(duck), 64): tg = duck[i:i + 64].max(); c = a_ if tg > y else r_; y = tg + (y - tg) * (c ** 64); gg[i:i + 64] = y
mg = 0.55 * (1 - 0.6 * gg); tt = np.arange(N) / SR; mg *= np.clip(tt / 0.8, 0, 1) * np.clip((DUR - 0.3 - tt) / 4.0, 0, 1)
mix = music * mg[:, None] + vo + sfx * 0.5; mix /= np.abs(mix).max() / 0.89
sf.write('out/mix5.wav', mix, SR, subtype='PCM_24'); print('mix5 ok', round(N / SR, 2), 's,', len(segs), 'music segments')
