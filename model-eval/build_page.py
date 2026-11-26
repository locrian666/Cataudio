#!/usr/bin/env python3
"""把评测结果 + 合成小样拼成 songs.html（表格：提示词 | 歌词 | 音频 | 其他信息）。"""
import json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sec(content, name):
    m = re.search(rf"##\s*{name}\s*\n(.*?)(?=\n##\s|\Z)", content, re.S)
    return m.group(1).strip() if m else ""


rows = []
for tag, f in (("off", "raw_results.json"), ("think", "raw_results_thinking.json")):
    for i, r in enumerate(json.loads((HERE / f).read_text())["results"], 1):
        c = r["content"]
        rows.append(dict(
            n=i, mode="思考关" if tag == "off" else "思考开",
            prompt=r["prompt"], case=r["case"],
            title=sec(c, "歌名"), style=sec(c, "风格"), lyrics=sec(c, "歌词"),
            reason=sec(c, "本猫的理由"), audio=f"audio/{tag}_{i}.mp4",
            total=r["total_s"], ttft=r["ttft_s"], tok=r["completion_tokens"], tps=r["tok_per_s"]))
rows.sort(key=lambda x: (x["n"], x["mode"] != "思考关"))
data = json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")
html = (HERE / "songs_template.html").read_text().replace("/*DATA*/[]", data)
(HERE / "songs.html").write_text(html)
print("wrote songs.html", len(rows), "rows")
