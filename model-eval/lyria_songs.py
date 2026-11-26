#!/usr/bin/env python3
"""把 Nemotron 写的歌词交给 Google Lyria 3.5 唱出来。

用法：
  export GEMINI_API_KEY=...          # 需要开通计费；脚本不会打印它
  python3 lyria_songs.py --smoke     # 只生成 1 首（思考关 #1）
  python3 lyria_songs.py             # 生成全部 16 首（已存在的跳过）
价格（官方定价页，2026-11）：lyria-3.5 每次请求约 $0.08。
"""
import argparse, base64, json, os, re, sys, time, urllib.request, urllib.error
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "audio_lyria"; OUT.mkdir(exist_ok=True)
MODEL = os.environ.get("LYRIA_MODEL", "lyria-3.5")
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"


def sec(c, name):
    m = re.search(rf"##\s*{name}\s*\n(.*?)(?=\n##\s|\Z)", c, re.S)
    return m.group(1).strip() if m else ""


def build_prompt(content, case):
    style = sec(content, "风格")
    lyrics = sec(content, "歌词").replace("[主歌]", "[Verse]").replace("[副歌]", "[Chorus]")
    return (
        f"创作一首约 1 分钟的中文歌曲，用普通话演唱，人声清晰。\n"
        f"音乐方向：{style}。场景：{case['city']}{case['time']}，{case['weather']}，"
        f"今天新闻气氛{case['news']}，听歌的人心情{case['mood']}。\n"
        f"请严格使用下面的歌词，不要改写：\n\n{lyrics}"
    )


def call(prompt):
    key = os.environ.get("GEMINI_API_KEY") or sys.exit("GEMINI_API_KEY 未设置")
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["AUDIO", "TEXT"]}}
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={
        "x-goog-api-key": key, "Content-Type": "application/json", "User-Agent": "model-eval/0.1"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.read().decode(errors='replace')[:800]}"}
    dt = time.perf_counter() - t0
    audio, texts = None, []
    for p in (data.get("candidates") or [{}])[0].get("content", {}).get("parts", []):
        if p.get("inlineData"): audio = p["inlineData"]
        elif p.get("text"): texts.append(p["text"])
    if not audio:
        return {"error": "无音频返回: " + json.dumps(data, ensure_ascii=False)[:800], "latency_s": round(dt, 1)}
    return {"audio": base64.b64decode(audio["data"]), "mime": audio.get("mimeType"),
            "text": "\n".join(texts), "latency_s": round(dt, 1), "usage": data.get("usageMetadata")}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--smoke", action="store_true"); a = ap.parse_args()
    jobs = []
    for tag, f in (("off", "raw_results.json"), ("think", "raw_results_thinking.json")):
        for i, r in enumerate(json.loads((HERE / f).read_text())["results"], 1):
            jobs.append((f"{tag}_{i}", r))
    if a.smoke: jobs = jobs[:1]
    log_path = OUT / "log.json"
    log = json.loads(log_path.read_text()) if log_path.exists() else {}
    for name, r in jobs:
        if (OUT / f"{name}.mp3").exists():
            print("skip", name); continue
        prompt = build_prompt(r["content"], r["case"])
        print("→", name, flush=True)
        res = call(prompt)
        entry = {"prompt": prompt, **{k: v for k, v in res.items() if k != "audio"}}
        if "audio" in res:
            (OUT / f"{name}.mp3").write_bytes(res["audio"])
            entry["bytes"] = len(res["audio"])
        log[name] = entry
        log_path.write_text(json.dumps(log, ensure_ascii=False, indent=1))
        print("  ", {k: entry.get(k) for k in ("latency_s", "mime", "bytes", "error")}, flush=True)
        if res.get("error") and "HTTP 4" in res["error"] and "429" not in res["error"]:
            sys.exit("请求被拒，停止。")


if __name__ == "__main__":
    main()
