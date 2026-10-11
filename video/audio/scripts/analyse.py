import json, subprocess, numpy as np, soundfile as sf
from scipy.signal import find_peaks
D = "/home/bajrangi/Wins/dhara/video/audio/"
subprocess.run(["ffmpeg","-loglevel","error","-y","-i",D+"music.mp3","-ac","1","-ar","22050",D+"_tmp/music.wav"],check=True)
a, sr = sf.read(D+"_tmp/music.wav"); dur = len(a)/sr
# onset envelope: positive spectral flux, hop 512
hop, n = 512, 2048
frames = np.lib.stride_tricks.sliding_window_view(a, n)[::hop] * np.hanning(n)
S = np.log1p(np.abs(np.fft.rfft(frames, axis=1)))
flux = np.maximum(0, np.diff(S, axis=0)).sum(1); flux = np.r_[0, flux]
flux = (flux - flux.mean()) / flux.std(); fps = sr/hop
# tempo: autocorrelation of onset envelope over 70-180 BPM
ac = np.correlate(flux, flux, "full")[len(flux)-1:]
lags = np.arange(len(ac)); bpm_of = 60*fps/np.maximum(lags,1)
m = (bpm_of >= 70) & (bpm_of <= 180)
lag = lags[m][np.argmax(ac[m])]
# refine lag with parabolic interpolation
y0,y1,y2 = ac[lag-1],ac[lag],ac[lag+1]; lagf = lag + 0.5*(y0-y2)/(y0-2*y1+y2)
bpm = 60*fps/lagf; period = 60/bpm
# phase: pick offset maximising onset sum on grid
t = np.arange(len(flux))/fps
best = max(np.linspace(0, period, 100, endpoint=False),
           key=lambda o: np.interp(np.arange(o, dur, period), t, flux).sum())
# first strong downbeat: first grid beat whose onset strength > 1.5 sd, then choose bar phase (4 beats) with max strength
grid = np.arange(best, min(dur, 210), period)
strength = np.interp(grid, t, flux)
bar_phase = max(range(4), key=lambda p: strength[p::4].sum())
downs = grid[bar_phase::4]
first_down = float(next(g for g,s in zip(downs, np.interp(downs,t,flux)) if s > 1.5))
# RMS per 2s window
w = 2*sr
rms = [float(20*np.log10(np.sqrt(np.mean(a[i:i+w]**2))+1e-9)) for i in range(0, len(a)-w+1, w)]
# energy rises: diff of 4s-smoothed RMS between consecutive 2s windows, top peaks
r = np.convolve(rms, np.ones(2)/2, "same"); rise = np.r_[0, np.diff(r)]
pk, _ = find_peaks(rise, distance=5)
top = sorted(pk, key=lambda i: -rise[i])[:6]
rises = sorted([{"time_s": float(i*2), "rise_db": round(float(rise[i]),2)} for i in top], key=lambda x: -x["rise_db"])
out = {"file":"music.mp3","duration_s":round(dur,2),"bpm":round(float(bpm),2),"beat_period_s":round(float(period),4),
       "first_grid_downbeat_s":round(float(downs[0]),3),"first_strong_downbeat_s":round(first_down,3),"downbeats_s":[round(float(x),3) for x in downs],
       "beats_s":[round(float(x),3) for x in grid],"rms_db_per_2s":[round(x,2) for x in rms],
       "biggest_energy_rises":rises,"notes":"beat grid from spectral-flux autocorrelation; downbeats assume 4/4; intro to ~74 s is soft, first strong (z>1.5 onset) downbeat coincides with the main drop"}
json.dump(out, open(D+"music_analysis.json","w"), indent=1)
print(out["duration_s"], out["bpm"], out["first_strong_downbeat_s"], rises)
print(' '.join(f"{x:.0f}" for x in rms))
