#!/usr/bin/env python3
"""把模型给出的 曲风/BPM/调性 渲染成一段纯器乐小样（无人声，只用标准库）。

Nemotron-3.5-Bolt-E4B 是纯文本模型，不会出音频；这里的音频是按它的参数
程序化合成的，用来"听"它的选择，不代表最终成品。
输出：audio/<off|think>_<n>.wav，再用 macOS afconvert 转成 .mp4。
"""
import json, math, random, re, struct, subprocess, wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
SR = 22050
OUT = HERE / "audio"; OUT.mkdir(exist_ok=True)
NOTES = {"C":0,"C#":1,"DB":1,"D":2,"D#":3,"EB":3,"E":4,"F":5,"F#":6,"GB":6,"G":7,"G#":8,"AB":8,"A":9,"A#":10,"BB":10,"B":11}


def parse(content):
    style = re.search(r"曲风[:：]\s*([^|｜\n]+)", content)
    bpm = re.search(r"BPM[:：]\s*(\d+)", content)
    key = re.search(r"调性[:：]\s*([A-Ga-g][#b♭]?)\s*(major|minor|大调|小调)?", content, re.I)
    root = NOTES.get((key.group(1)[0].upper() + key.group(1)[1:].replace("♭", "b").upper()) if key else "C", 0)
    minor = bool(key and key.group(2) and key.group(2).lower() in ("minor", "小调"))
    return (style.group(1).strip() if style else "Pop"), int(bpm.group(1)) if bpm else 90, root, minor


def hz(m): return 440.0 * 2 ** ((m - 69) / 12)


def render(style, bpm, root, minor, seed):
    rnd = random.Random(seed)
    s = style.lower()
    lofi = "lo" in s; trip = "trip" in s; folk = "folk" in s; city = "city" in s
    beat = 60.0 / bpm; bars = 8; n = int(SR * beat * 4 * bars) + SR
    buf = [0.0] * n

    def add(t0, dur, f, amp, kind="sine", atk=0.01, rel=0.2):
        i0 = int(t0 * SR); ln = int((dur + rel) * SR)
        ph = 0.0; inc = 2 * math.pi * f / SR
        for k in range(ln):
            i = i0 + k
            if i >= n: break
            t = k / SR
            env = min(1.0, t / atk) if t < atk else (1.0 if t < dur else max(0.0, 1 - (t - dur) / rel))
            if kind == "sine": v = math.sin(ph)
            elif kind == "pad": v = math.sin(ph) + 0.35 * math.sin(2 * ph) + 0.15 * math.sin(3 * ph + 0.3)
            elif kind == "pluck": v = (math.sin(ph) + 0.4 * math.sin(2 * ph)) * math.exp(-t * 4)
            else: v = math.sin(ph)
            buf[i] += amp * env * v; ph += inc

    def kick(t0, amp=0.9):
        i0 = int(t0 * SR); ph = 0.0
        for k in range(int(0.35 * SR)):
            if i0 + k >= n: break
            t = k / SR; f = 45 + 110 * math.exp(-t * 30)
            ph += 2 * math.pi * f / SR
            buf[i0 + k] += amp * math.exp(-t * 9) * math.sin(ph)

    def noise(t0, dur, amp, decay):
        i0 = int(t0 * SR); last = 0.0
        for k in range(int(dur * SR)):
            if i0 + k >= n: break
            x = rnd.uniform(-1, 1); hp = x - last; last = x
            buf[i0 + k] += amp * math.exp(-(k / SR) * decay) * hp

    base = 48 + root  # C3 区域
    prog = [0, 8, 3, 10] if minor else [0, 7, 9, 5]       # i-VI-III-VII / I-V-vi-IV
    qual = ([0, 3, 7], [0, 4, 7], [0, 4, 7], [0, 4, 7]) if minor else ([0, 4, 7], [0, 4, 7], [0, 3, 7], [0, 4, 7])
    scale = [0, 3, 5, 7, 10] if minor else [0, 2, 4, 7, 9]
    swing = 0.12 * beat if lofi else 0.0
    for bar in range(bars):
        t = bar * 4 * beat; c = bar % 4
        r = base + prog[c]
        for iv in qual[c]:
            add(t, 4 * beat * 0.95, hz(r + 12 + iv), 0.06, "pad", atk=0.4 if not city else 0.05, rel=0.6)
        # bass
        hits = [0, 1.5, 2, 3.5] if city else ([0, 2.5] if trip else [0, 2])
        for h in hits: add(t + h * beat, beat * (0.9 if city else 1.6), hz(r - 12), 0.22, "sine", rel=0.1)
        # drums
        if not folk:
            for h in ([0, 1.75, 2.5] if trip else ([0, 2] if not city else [0, 1, 2, 3])):
                kick(t + h * beat, 0.8 if trip else 0.7)
            for h in (1, 3): noise(t + h * beat, 0.25, 0.35 if trip else 0.25, 18)
            for e in range(8):
                off = swing if e % 2 else 0
                noise(t + e * beat / 2 + off, 0.05, 0.08 if not lofi else 0.05, 60)
        # melody / arp
        step = 0.5 if (city or folk) else 1.0
        k = 0.0
        while k < 4:
            if rnd.random() < (0.85 if bar >= 2 else 0.5):
                deg = rnd.choice(scale) + rnd.choice([0, 12])
                add(t + k * beat + (swing if (k * 2) % 2 else 0), beat * step * 0.8,
                    hz(base + 24 + deg), 0.12, "pluck" if (folk or lofi) else "sine", rel=0.15)
            k += step
    if lofi:  # 黑胶噪声
        for i in range(n):
            if rnd.random() < 0.0008: buf[i] += rnd.uniform(-0.3, 0.3)
            buf[i] += rnd.uniform(-0.004, 0.004)
    # 一阶低通 + 归一化 + 淡出
    a = 0.35 if lofi else (0.5 if trip else 0.7); y = 0.0
    for i in range(n): y += a * (buf[i] - y); buf[i] = y
    peak = max(abs(v) for v in buf) or 1
    fade = int(1.5 * SR)
    for i in range(n):
        g = 0.85 / peak * (min(1.0, (n - i) / fade))
        buf[i] = max(-1.0, min(1.0, buf[i] * g))
    return buf


def save(name, buf):
    wav = OUT / f"{name}.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", int(v * 32767)) for v in buf))
    m4a = OUT / f"{name}.mp4"
    subprocess.run(["afconvert", "-f", "mp4f", "-d", "aac", "-b", "64000", str(wav), str(m4a)], check=True)
    wav.unlink()
    return m4a


def main():
    meta = []
    for tag, f in (("off", "raw_results.json"), ("think", "raw_results_thinking.json")):
        for i, r in enumerate(json.loads((HERE / f).read_text())["results"], 1):
            style, bpm, root, minor = parse(r["content"])
            p = save(f"{tag}_{i}", render(style, bpm, root, minor, seed=f"{tag}{i}"))
            print(tag, i, style, bpm, root, "minor" if minor else "major", p.name, p.stat().st_size, flush=True)
            meta.append(dict(tag=tag, i=i, style=style, bpm=bpm, root=root, minor=minor, file=f"audio/{p.name}"))
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
