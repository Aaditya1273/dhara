import numpy as np, soundfile as sf
from scipy.signal import resample_poly
SR = 48000; DUR = 75.5; N = int(SR * DUR)
L = {1: 0.5, 2: 2.75, 3: 5.0, 4: 12.6, 5: 19.8, 6: 30.4, 7: 41.3, 8: 46.0, 9: 52.6, 10: 59.5, 11: 64.2, 12: 70.1}
def load(p):
    x, sr = sf.read(p, dtype='float32', always_2d=True)
    if sr != SR: x = resample_poly(x, SR, sr, axis=0).astype(np.float32)
    return np.repeat(x, 2, axis=1) if x.shape[1] == 1 else x
def place(b, x, t, gn=1.0):
    i = int(t * SR); j = min(N, i + len(x)); b[i:j] += x[:j - i] * gn
mix = np.zeros((N, 2), np.float32)
for n, t in L.items(): place(mix, load(f'audio/v4/vo_{n:02d}.wav'), t)
S = lambda n: load(f'audio/sfx_{n}.wav')
for n, t, gn in [('ping', 0.05, .25), ('click', 0.5, .5), ('whoosh', 11.5, .35), ('ping', 12.6, .3), ('whoosh', 19.1, .3), ('whoosh', L[6] - 0.3, .3),
                 ('ping', L[6] + 7.3, .3), ('whoosh', 40.7, .3), ('click', L[7] + 0.8, .7), ('click', L[8] + 0.2, .4), ('whoosh', L[10] - 0.2, .3), ('whoosh', 69.7, .3)]:
    place(mix, S(n), t, gn)
for k in range(4): place(mix, S('type'), L[7] + 1.05 + k * 0.1, .5)
mix /= np.abs(mix).max() / 0.89; sf.write('out/mix4_vo_sfx.wav', mix, SR, subtype='PCM_24'); print('mix ok')
