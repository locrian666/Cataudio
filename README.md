# 猫抓音乐 · Cataudio

一只住在唱片堆里的像素黑猫“抓抓”，根据天气、时间、你的心情，从唱片堆里给你抓一首现场合成的歌。

线上地址：https://cataudio.pages.dev

## 功能

- **抓歌**：按天气、气温、时段、心情和新闻情绪合成音乐描述（风格、BPM、调性），在浏览器里用 Web Audio 现场合成；每天 3 次。
- **和抓抓聊天**：窗户下面的输入栏，聊天记录可上下滑动、保存在本机。抓抓会按聊天内容换心情、点风格、换歌或暂停。
- **大模型**：歌名、抓歌理由和聊天回复由后端 `/api/chat` 调用通义千问（或 Claude）生成；没有配置密钥或出错时退回内置台词。
- **养猫**：喂饭、喂水，投喂次数解锁皮肤（黑猫、蓝灰、橘子、奶白、暹罗）。
- **DLC「抓抓的小日子」**（原型里是模拟购买）：4 顶帽子，以及 9 个闲着时会随机做的陪伴动作。
- **设置**：自动定位、城市、中文 / English、昵称、测试码。

## 目录

| 路径 | 说明 |
|---|---|
| `prototype/index.html` | 整个前端，单文件（精灵图以 data URI 内嵌） |
| `deploy/` | 发布到 Cloudflare Pages 的静态文件（`prototype/index.html` 的副本） |
| `functions/api/chat.js` | Pages Function：聊天和歌名生成，每个 IP 每天限次 |
| `functions/api/owner.js` | 校验站长测试码 |
| `wrangler.jsonc` | Cloudflare Pages 配置（KV 绑定用于限次） |
| `model-eval/` | 用大模型写歌词、生成歌曲的评测脚本和结果 |

## 部署

```bash
npm install
cp prototype/index.html deploy/index.html
wrangler pages deploy --branch main
```

需要在 Cloudflare 后台（`wrangler pages secret put <名字> --project-name cataudio`）设置的密钥：

- `QWEN_API_KEY`：通义千问密钥（可选 `QWEN_BASE_URL`、`QWEN_MODEL`，默认阿里云百炼 `qwen-plus`）
- 或 `ANTHROPIC_API_KEY`：使用 Claude
- `OWNER_TOKEN`：站长测试码，带上它不限次数、全部解锁

密钥不进仓库。
