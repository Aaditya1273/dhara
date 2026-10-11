import json, subprocess
dur = lambda f: float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f], capture_output=True, text=True).stdout)
SCENES = [[1], [2, 3], [4, 5], [6], [7, 8], [9, 10, 11, 12, 13], [14, 15], [16]]
GAP_IN = {10: 0.5, 11: 0.5, 12: 0.5, 13: 0.5, 8: 0.35, 3: 0.3, 5: 0.3, 15: 0.35}
t = 0.0; lines = {}; scenes = []
for si, sc in enumerate(SCENES):
    for k, n in enumerate(sc):
        if k == 0: t += 0.9 if si == 0 else 0.75
        else: t += GAP_IN.get(n, 0.35)
        d = dur(f'audio/fast/vo_L{n:02d}.wav'); lines[n] = [round(t, 3), round(d, 3)]
        if k == 0: scenes.append(round(0 if si == 0 else t - 0.45, 3))
        t += d
total = round(t + 3.4, 3)
bounds = [[scenes[i], scenes[i + 1] if i + 1 < len(scenes) else total] for i in range(len(scenes))]
json.dump({'lines': lines, 'scenes': bounds, 'total': total}, open('timeline.json', 'w'), indent=1)
print('total', total); [print(i + 1, b) for i, b in enumerate(bounds)]
