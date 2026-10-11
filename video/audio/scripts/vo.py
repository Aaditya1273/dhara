import sys, numpy as np, soundfile as sf
from kokoro_onnx import Kokoro
D = "/home/bajrangi/Wins/dhara/video/audio/"
LINES = {
1:"Every afternoon, the sun climbs over a hostel roof, and heats the water hundreds of students will use tonight.",
2:"Heat speeds up the loss of chlorine in stored water. But the only record most tanks have, is a line in a register. Cleaned.",
3:"It can't tell you how warm the water is. Whether any chlorine is left. Who checked the work. Or what the lab found.",
4:"This is DHARA. A water evidence ledger for hostels, schools and campuses.",
5:"It measures what's happening inside the tank, tells staff which tank to test next, and keeps a traceable record of every response.",
6:"A low-cost probe publishes every reading to AWS IoT Core, over TLS, with its own device certificate. IoT rules forward it to DHARA on Amazon EC2, and archive the raw message in Amazon S3.",
7:"And this is running for real. We had no hardware before the deadline, so the ESP32 is simulated on Wokwi. Everything after it is real AWS.",
8:"Every five seconds, a reading leaves the simulated board, reaches IoT Core, lands in S3, and DHARA stores it on EC2, within seconds.",
9:"Inside DHARA, the warden sees every tank at a glance, with each reading's source and time.",
10:"Testing priority combines reading age, thresholds and the heat forecast, and explains every rule it fires.",
11:"A technician records free chlorine at zero point one five. It's below the minimum, so DHARA escalates it for warden review.",
12:"Maintenance is submitted with photos. Every file is fingerprinted with SHA two fifty-six, and the person who did the work can never approve it.",
13:"Anyone can scan the tank's QR code and see its status, without private details.",
14:"No guessing which tank to test. No lost evidence. Every decision, named and timed.",
15:"And DHARA never claims the water is safe. It shows what was measured, what was done, and what still needs doing.",
16:"DHARA. Because water deserves more than a record.",
}
voice = sys.argv[1] if len(sys.argv) > 1 else "am_michael"
only = [int(x) for x in sys.argv[2:]] or list(LINES)
k = Kokoro(D+"models/kokoro-v1.0.onnx", D+"models/voices-v1.0.bin")
for i in only:
    t = LINES[i]
    a, sr = k.create(t, voice=voice, speed=0.95, lang="en-us")
    a = np.asarray(a, dtype=np.float64)
    # trim to ~50 ms of silence each side (threshold relative to peak)
    env = np.abs(a) > 0.02 * np.abs(a).max()
    idx = np.flatnonzero(env); pad = int(0.05*sr)
    a = a[max(0, idx[0]-pad): idx[-1]+pad]
    # RMS normalise toward ~-16 LUFS-ish (speech RMS ~ -19 dBFS), cap peak at -1 dBFS
    a *= 10**(-19/20) / np.sqrt(np.mean(a**2))
    a *= min(1.0, 10**(-1/20) / np.abs(a).max())
    sf.write(f"{D}vo_L{i:02d}.wav", a.astype(np.float32), sr, subtype="PCM_16")
    w = len(t.split()); d = len(a)/sr
    print(f"L{i:02d} sr={sr} dur={d:.2f}s words={w} wps={w/d:.2f} peak={20*np.log10(np.abs(a).max()):.1f}dB", flush=True)
