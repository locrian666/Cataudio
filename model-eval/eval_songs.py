#!/usr/bin/env python3
"""猫抓音乐 × Nemotron-3.5-Bolt-E4B 歌曲生成评测。

只用标准库。调用 OpenAI 兼容的 /chat/completions（默认 NVIDIA 托管 API），
流式读取以测首 token 延迟和 tokens/s，结果写进 report.md + raw_results.json。

用法：
  export NVIDIA_API_KEY=...        # 自己在 shell 里设，脚本不会打印它
  python3 eval_songs.py --smoke    # 只发一条短请求
  python3 eval_songs.py            # 跑全部 8 条
  python3 eval_songs.py --thinking # 打开思考模式再跑一次（输出 report_thinking.md）
"""
import argparse, json, os, sys, time, urllib.request, urllib.error
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE_URL = os.environ.get("EVAL_BASE_URL", "https://integrate.api.nvidia.com/v1")
MODEL = os.environ.get("EVAL_MODEL", "nvidia/nemotron-3.5-bolt-e4b")

SYSTEM = (
    "你是「猫抓音乐」里的一只像素黑猫，蓝眼睛，有点傲娇，自称「本猫」。"
    "你根据今天的天气、新闻气氛、城市时间和用户心情，为用户写一首原创歌曲的创作方案。"
    "只用简体中文回答（风格/调性等音乐术语可用英文）。严格按以下格式输出，不要多余内容：\n"
    "## 歌名\n<歌名>\n"
    "## 风格\n曲风：<曲风> | BPM：<数字> | 调性：<如 C major / A minor>\n"
    "## 歌词\n[主歌]\n<4-8 行>\n[副歌]\n<4-6 行，尽量押韵>\n"
    "## 本猫的理由\n<一句话，用本猫的傲娇口吻解释为什么这样选，要提到具体信号>"
)

CASES = [
    dict(city="上海", time="早上 7:40", weather="晴", news="轻松", mood="开心"),
    dict(city="上海", time="深夜 1:15", weather="小雨", news="沉重", mood="emo"),
    dict(city="伦敦", time="下午 4:00", weather="阴天", news="紧张", mood="焦虑"),
    dict(city="东京", time="晚上 9:30", weather="下雪", news="轻松", mood="放空"),
    dict(city="东京", time="中午 12:10", weather="晴", news="紧张", mood="开心"),
    dict(city="伦敦", time="早上 8:20", weather="小雨", news="轻松", mood="放空"),
    dict(city="上海", time="傍晚 6:45", weather="阴天", news="沉重", mood="焦虑"),
    dict(city="东京", time="凌晨 3:00", weather="下雪", news="沉重", mood="emo"),
]


def user_prompt(c):
    return (f"现在是{c['city']}{c['time']}，天气：{c['weather']}。"
            f"今天的新闻整体气氛：{c['news']}。用户现在的心情：{c['mood']}。"
            "请给出这首歌的创作方案。")


def chat(messages, thinking, max_tokens):
    key = os.environ.get("NVIDIA_API_KEY")
    if not key:
        sys.exit("NVIDIA_API_KEY 未设置")
    body = {
        "model": MODEL, "messages": messages, "stream": True,
        "temperature": 1.0, "top_p": 0.95, "max_tokens": max_tokens,
        "stream_options": {"include_usage": True},
        "chat_template_kwargs": {"enable_thinking": thinking},
    }
    req = urllib.request.Request(
        f"{BASE_URL}/chat/completions", data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "Accept": "text/event-stream", "User-Agent": "model-eval/0.1"})
    t0 = time.perf_counter(); ttft = None
    content, reasoning, usage, chunks = [], [], None, 0
    try:
        resp = urllib.request.urlopen(req, timeout=300)
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.read().decode(errors='replace')[:500]}"}
    with resp:
        for raw in resp:
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            ev = json.loads(data)
            if ev.get("usage"):
                usage = ev["usage"]
            for ch in ev.get("choices") or []:
                d = ch.get("delta") or {}
                r = d.get("reasoning_content") or d.get("reasoning")
                c = d.get("content")
                if (r or c) and ttft is None:
                    ttft = time.perf_counter() - t0
                if r: reasoning.append(r)
                if c: content.append(c); chunks += 1
    total = time.perf_counter() - t0
    out_tok = (usage or {}).get("completion_tokens")
    gen_time = total - (ttft or 0)
    return {
        "content": "".join(content), "reasoning": "".join(reasoning),
        "ttft_s": round(ttft or 0, 3), "total_s": round(total, 3),
        "prompt_tokens": (usage or {}).get("prompt_tokens"),
        "completion_tokens": out_tok,
        "tok_per_s": round(out_tok / gen_time, 1) if out_tok and gen_time > 0 else None,
        "content_chunks": chunks,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--thinking", action="store_true")
    ap.add_argument("--max-tokens", type=int, default=1500)
    a = ap.parse_args()

    if a.smoke:
        r = chat([{"role": "user", "content": "用一句中文介绍你自己。"}], False, 100)
        print(json.dumps(r, ensure_ascii=False, indent=2)); return

    results = []
    for i, c in enumerate(CASES, 1):
        print(f"[{i}/{len(CASES)}] {c}", flush=True)
        r = chat([{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": user_prompt(c)}], a.thinking, a.max_tokens)
        r["case"] = c; r["prompt"] = user_prompt(c)
        print("   ", {k: r.get(k) for k in ("ttft_s", "total_s", "completion_tokens", "tok_per_s", "error")}, flush=True)
        results.append(r)

    suffix = "_thinking" if a.thinking else ""
    (HERE / f"raw_results{suffix}.json").write_text(
        json.dumps({"model": MODEL, "base_url": BASE_URL, "thinking": a.thinking,
                    "system": SYSTEM, "results": results}, ensure_ascii=False, indent=2))

    ok = [r for r in results if not r.get("error")]
    def avg(k):
        v = [r[k] for r in ok if r.get(k) is not None]
        return round(sum(v) / len(v), 2) if v else None
    lines = [f"# 原始输出：{MODEL}（thinking={'on' if a.thinking else 'off'}）", "",
             f"运行时间：{datetime.now():%Y-%m-%d %H:%M} · 端点：{BASE_URL} · temperature=1.0, top_p=0.95", "",
             f"平均：首 token {avg('ttft_s')}s · 总耗时 {avg('total_s')}s · 输出 {avg('completion_tokens')} tokens · {avg('tok_per_s')} tok/s · 成功 {len(ok)}/{len(results)}", "",
             "## System prompt", "", "```", SYSTEM, "```", ""]
    for i, r in enumerate(results, 1):
        c = r["case"]
        lines += [f"## {i}. {c['city']} {c['time']} · {c['weather']} · 新闻{c['news']} · 心情{c['mood']}", "",
                  f"首 token {r.get('ttft_s')}s · 总 {r.get('total_s')}s · {r.get('completion_tokens')} tokens · {r.get('tok_per_s')} tok/s", ""]
        if r.get("error"):
            lines += ["**错误：** " + r["error"], ""]; continue
        if r.get("reasoning"):
            lines += ["<details><summary>思考过程</summary>", "", r["reasoning"], "", "</details>", ""]
        lines += [r["content"].strip(), ""]
    (HERE / f"raw_outputs{suffix}.md").write_text("\n".join(lines))
    print("写入", HERE / f"raw_outputs{suffix}.md")


if __name__ == "__main__":
    main()
