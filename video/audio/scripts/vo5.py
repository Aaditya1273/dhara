import numpy as np, soundfile as sf, json
from kokoro_onnx import Kokoro
D = "/home/bajrangi/Wins/dhara/video/audio/"
LINES = {
1: 'This tank was cleaned last month.',
2: 'So, is the water safe today?',
3: 'Nobody can tell you.',
4: 'Across India, hostels, schools and campuses store their drinking water in rooftop tanks like these.',
5: 'NITI Aayog reports that about two lakh people die every year in India, due to inadequate access to safe water.',
6: "India's drinking water standard asks for at least zero point two milligrams per litre of free chlorine, tested at the tap. That residual is what keeps protecting the water after it leaves the plant.",
7: 'But rooftop tanks bake in the sun. A 2024 review in Water Research warns that keeping protective chlorine levels can be challenging at high temperatures.',
8: "And when someone asks what was checked, an institution has a register that says cleaned. Photos on someone's phone. A lab report, lost in email.",
9: 'Meet DHARA. A water evidence ledger for hostels, schools and campuses.',
10: "It measures what's happening inside the tank, tells staff which tank to test next, and keeps proof of every response.",
11: 'A low-cost probe publishes readings over MQTT to AWS IoT Core, with its own device certificate. IoT rules archive every message in Amazon S3, and forward it to DHARA on Amazon EC2.',
12: 'This is not a mock-up. We recorded it live. A simulated ESP32 on Wokwi sends thirty-four point two degrees.',
13: "Every five seconds, a new object lands in S3, and DHARA's database on EC2 receives the same reading, within a second.",
14: 'Inside DHARA, the warden sees what needs attention today.',
15: 'A technician records free chlorine at zero point one five.',
16: "That's below the minimum. Testing priority flags the tank as urgent, and explains exactly which rule fired.",
17: 'Maintenance comes with real photos. Each file is fingerprinted with SHA two fifty-six, and anyone can re-check it later.',
18: 'The person who did the work can never approve it. A warden reviews it, and the decision is named and timed.',
19: 'Every open follow-up has an owner and a due date, until someone records what was done.',
20: "And anyone can scan the tank's QR code to see where it stands. No login. No private details.",
21: 'Paper registers record the cleaning, but not the water. Dashboards show readings, but not who acted. DHARA connects the reading, the decision, and the proof.',
22: "And it's honest by design. It never claims the water is safe.",
23: 'The global market for water quality analysers alone was estimated at four point three billion dollars in 2024.',
24: 'Because water deserves more than a record.',
}
k = Kokoro(D + "models/kokoro-v1.0.onnx", D + "models/voices-v1.0.bin")
out = {}
for i, t in LINES.items():
    a, sr = k.create(t, voice="am_michael", speed=1.05, lang="en-us")
    a = np.asarray(a, dtype=np.float64); env = np.abs(a) > 0.02 * np.abs(a).max(); idx = np.flatnonzero(env); pad = int(0.04 * sr)
    a = a[max(0, idx[0] - pad): idx[-1] + pad]; a *= 10 ** (-19 / 20) / np.sqrt(np.mean(a ** 2)); a *= min(1.0, 10 ** (-1 / 20) / np.abs(a).max())
    sf.write(f"{D}v5/vo_{i:02d}.wav", a.astype(np.float32), sr, subtype="PCM_16"); out[i] = round(len(a) / sr, 3)
    print(i, out[i], flush=True)
json.dump(out, open(D + "v5/durations.json", "w"))
