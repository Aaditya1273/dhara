import numpy as np, soundfile as sf
from scipy.signal import butter, sosfilt
D = "/home/bajrangi/Wins/dhara/video/audio/"; SR = 48000; rng = np.random.default_rng(7)
T = lambda d: np.arange(int(d*SR))/SR
def bp(x, lo, hi): return sosfilt(butter(2, [lo, hi], "band", fs=SR, output="sos"), x)
def lp(x, f): return sosfilt(butter(2, f, "low", fs=SR, output="sos"), x)
def sweep_noise(d, f0, f1, q=0.6):
    # time-varying band-pass via short blocks
    n = rng.standard_normal(int(d*SR)); out = np.zeros_like(n); blk = 512
    for i in range(0, len(n), blk):
        f = f0 * (f1/f0) ** (i/len(n)); lo, hi = f*(1-q/2), min(f*(1+q/2), SR/2-100)
        out[i:i+blk] = bp(n[max(0,i-2048):i+blk], lo, hi)[-len(n[i:i+blk]):]
    return out
def save(name, x, width=0.0):
    # stereo with slight decorrelation (delay R by width ms), peak -3 dBFS, 5 ms fades
    d = int(width*SR/1000); L = x; R = np.r_[np.zeros(d), x[:len(x)-d]] if d else x
    s = np.stack([L, R], 1); f = min(240, len(x)//4)
    s[:f] *= np.linspace(0,1,f)[:,None]; s[-f:] *= np.linspace(1,0,f)[:,None]
    s *= 10**(-3/20) / np.abs(s).max(); sf.write(D+name, s.astype(np.float32), SR, subtype="PCM_24")
t = T(0.7); env = np.sin(np.pi*t/0.7)**2
save("sfx_whoosh.wav", sweep_noise(0.7, 300, 4000) * env, 0.6)
t = T(1.2); env = (t/1.2)**3
save("sfx_whoosh_rev.wav", sweep_noise(1.2, 400, 6000) * env + 0.15*np.sin(2*np.pi*(110*t + 60*t**2))*env, 0.8)
t = T(1.5); f = 40 + 30*np.exp(-t/0.12); ph = 2*np.pi*np.cumsum(f)/SR
boom = np.sin(ph)*np.exp(-t/0.45); trans = lp(rng.standard_normal(len(t)), 900)*np.exp(-t/0.015)*0.6
tail = lp(rng.standard_normal(len(t)), 200)*np.exp(-t/0.5)*0.15
save("sfx_impact.wav", np.tanh(1.5*(boom+trans+tail)), 0.3)
t = T(2.5); env = (t/2.5)**2
tone = sum(np.sin(2*np.pi*(f0*t + f0*0.6*t**2/2.5))/k for k,f0 in [(1,220),(2,330),(3,440)])
save("sfx_riser.wav", (sweep_noise(2.5, 500, 8000)*1.5 + 0.25*tone) * env, 0.7)
t = T(0.5); f = 800*(1800/800)**np.minimum(t/0.06, 1); ph = 2*np.pi*np.cumsum(f)/SR
save("sfx_drop.wav", np.sin(ph)*np.exp(-t/0.05)*(1-np.exp(-t/0.002)), 0.2)
t = T(1.5); x = np.zeros_like(t)
for _ in range(40):  # scattered tiny high droplets under a soft shimmering band
    s0 = rng.uniform(0, 1.35); fr = rng.uniform(1500, 3500); tt = t - s0; m = tt >= 0
    x[m] += rng.uniform(0.2, 0.6)*np.sin(2*np.pi*fr*(1+0.5*np.minimum(tt[m]/0.03,1))*tt[m])*np.exp(-tt[m]/0.025)
x += 0.4*bp(rng.standard_normal(len(t)), 2000, 6000)*(0.6+0.4*np.sin(2*np.pi*7*t))
save("sfx_ripple.wav", x*np.sin(np.pi*t/1.5), 1.2)
t = T(0.04); save("sfx_click.wav", (bp(rng.standard_normal(len(t)), 2000, 9000)*np.exp(-t/0.002) + 0.5*np.sin(2*np.pi*3000*t)*np.exp(-t/0.004)), 0)
t = T(0.03); save("sfx_type.wav", (bp(rng.standard_normal(len(t)), 800, 5000)*np.exp(-t/0.004) + 0.3*np.sin(2*np.pi*180*t)*np.exp(-t/0.006)), 0)
t = T(0.6); ping = sum(a*np.sin(2*np.pi*f*t)*np.exp(-t/d) for a,f,d in [(1,1320,0.18),(0.4,2640,0.09),(0.25,1980,0.12)])
save("sfx_ping.wav", ping*(1-np.exp(-t/0.003)), 0.4)
