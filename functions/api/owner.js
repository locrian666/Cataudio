// 页面用来确认测试码对不对：对了就进入测试模式（不限次数、全部解锁）
import { isOwner } from "./chat.js";

export async function onRequestPost({ request, env }){
  return new Response(JSON.stringify({ ok: isOwner(request, env) }), {
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" }
  });
}
export const onRequest = () => new Response(JSON.stringify({ error: "method" }), { status: 405, headers: { "content-type": "application/json" } });
