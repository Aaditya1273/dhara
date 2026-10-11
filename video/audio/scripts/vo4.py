import numpy as np, soundfile as sf, json
from kokoro_onnx import Kokoro
D = "/home/bajrangi/Wins/dhara/video/audio/"
LINES = {
1: "This tank was cleaned last month.",
2: "So, is the water safe today?",
3: "Nobody can tell you. Heat drains chlorine from rooftop tanks, and a cleaning record can't see inside one.",
4: "Meet DHARA. It measures the tank, tells staff what to test next, and keeps proof of every response.",
5: "This is the real pipeline. A simulated ESP32 on Wokwi publishes to AWS IoT Core, with its own device certificate.",
6: "An IoT rule archives every message in Amazon S3, and forwards it to DHARA on Amazon EC2. The same reading, seconds apart.",
7: "In DHARA, a technician records free chlorine at zero point one five.",
8: "That's below the minimum. Testing priority flags the tank as urgent, and shows exactly why.",
9: "Every piece of evidence is fingerprinted with SHA two fifty-six, and nobody can approve their own work.",
10: "And anyone can scan the tank's QR code to see where it stands.",
11: "DHARA never claims the water is safe. It shows what was measured, and what still needs doing.",
12: "Because water deserves more than a record.",
}
k = Kokoro(D + "models/kokoro-v1.0.onnx", D + "models/voices-v1.0.bin")
out = {}
for i, t in LINES.items():
    a, sr = k.create(t, voice="am_michael", speed=1.08, lang="en-us")
    a = np.asarray(a, dtype=np.float64); env = np.abs(a) > 0.02 * np.abs(a).max(); idx = np.flatnonzero(env); pad = int(0.04 * sr)
    a = a[max(0, idx[0] - pad): idx[-1] + pad]; a *= 10 ** (-19 / 20) / np.sqrt(np.mean(a ** 2)); a *= min(1.0, 10 ** (-1 / 20) / np.abs(a).max())
    sf.write(f"{D}v4/vo_{i:02d}.wav", a.astype(np.float32), sr, subtype="PCM_16"); out[i] = round(len(a) / sr, 3)
    print(i, out[i], flush=True)
json.dump(out, open(D + "v4/durations.json", "w"))
