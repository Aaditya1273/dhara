import numpy as np, soundfile as sf, subprocess, io
from scipy.signal import resample_poly
SR = 48000; DUR = 158.5; N = int(SR * DUR)
A = 'audio/'
def load(path):
    if path.endswith('.mp3'):
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'f32le', '-ac', '2', '-ar', str(SR), '-'], capture_output=True).stdout
        return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()
    x, sr = sf.read(path, dtype='float32', always_2d=True)
    if sr != SR: x = resample_poly(x, SR, sr, axis=0).astype(np.float32)
    if x.shape[1] == 1: x = np.repeat(x, 2, axis=1)
    return x
def place(buf, x, t, gain=1.0):
    i = int(t * SR); j = min(N, i + len(x))
    if i < N: buf[i:j] += x[:j - i] * gain
vo = np.zeros((N, 2), np.float32); sfx = np.zeros((N, 2), np.float32)
VO = {1: 1.2, 2: 11.0, 3: 20.6, 4: 30.2, 5: 35.9, 6: 46.2, 7: 65.0, 8: 77.4, 9: 90.0, 10: 96.7, 11: 105.0, 12: 114.4, 13: 125.0, 14: 132.2, 15: 138.8, 16: 148.6}
for k, t in VO.items(): place(vo, load(f'{A}vo_L{k:02d}.wav'), t, 1.0)
S = {n: load(f'{A}sfx_{n}.wav') for n in ['whoosh', 'whoosh_rev', 'impact', 'riser', 'drop', 'ripple', 'click', 'type', 'ping']}
ev = [('drop', 1.82, .9), ('ripple', 1.95, .7), ('impact', 1.9, .5), ('whoosh_rev', 2.0, .5), ('whoosh', 10.35, .6),
      ('impact', 19.0, .8), ('ping', 20.6, .35), ('ping', 22.5, .35), ('ping', 24.2, .35), ('ping', 26.0, .35),
      ('riser', 26.4, .5), ('whoosh', 28.5, .7), ('impact', 31.0, .9), ('ripple', 31.1, .4), ('whoosh', 45.4, .6),
      ('ping', 49.2, .3), ('ping', 54.8, .3), ('ping', 56.6, .3), ('whoosh_rev', 73.7, .6), ('impact', 74.97, 1.0),
      ('ping', 86.9, .4), ('whoosh', 89.2, .6), ('click', 97.7, .9), ('click', 106.5, .9), ('whoosh', 124.1, .5),
      ('whoosh', 131.2, .6), ('impact', 139.8, .8), ('drop', 147.95, .9), ('ripple', 148.1, .7), ('impact', 148.2, .5)]
for n, t, gn in ev: place(sfx, S[n], t, gn)
for t0, dur in [(76.0, 1.7), (78.6, 1.3), (81.4, 1.2)]:  # terminal typing
    for k in range(int(dur / 0.07)): place(sfx, S['type'], t0 + k * 0.07 + (k % 3) * 0.008, .45)
for t in [106.9, 107.22, 107.54, 107.86]: place(sfx, S['type'], t, .6)
music = load(A + 'music.mp3')[:N]
if len(music) < N: music = np.pad(music, ((0, N - len(music)), (0, 0)))
# duck the music under the voice: envelope follower with fast attack, slow release
env = np.abs(vo).max(axis=1); win = int(0.05 * SR); env = np.convolve(env, np.ones(win) / win, 'same')
duck = np.clip(env / 0.05, 0, 1); g = np.empty_like(duck); a, r = np.exp(-1 / (0.03 * SR)), np.exp(-1 / (0.45 * SR)); y = 0.0
for i in range(0, len(duck), 64):  # block-wise smoothing for speed
    target = duck[i:i + 64].max(); c = a if target > y else r; y = target + (y - target) * (c ** 64); g[i:i + 64] = y
mg = 0.62 * (1 - 0.55 * g)
t = np.arange(N) / SR; mg *= np.clip((DUR - 1.0 - t) / 6.0, 0, 1)  # music fades out over the last seconds
mix = music * mg[:, None] + vo * 1.0 + sfx * 0.55
mix /= max(1e-6, np.abs(mix).max()) / 0.89
sf.write('out/mix.wav', mix, SR, subtype='PCM_24')
print('mix ok', mix.shape[0] / SR, 's')
