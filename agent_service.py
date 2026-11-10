import os
import sys
import io

os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import json
import traceback
import jieba
import requests
from rank_bm25 import BM25Okapi
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from workflow import app as multi_agent_app
from tools import send_wechat_alert
from config import INTERNAL_TOKEN, API_KEY, BASE_URL, MODEL_FIXER

app = FastAPI(title="Agent Internal Service")


# ==================== 通用 DTO ====================
class HistoryMessage(BaseModel):
    role: str
    content: str


class AgentStreamRequest(BaseModel):
    trace_id: str
    session_id: str
    user_query: str
    user_memory: str = "暂无记忆"
    history: List[HistoryMessage] = []


class MemoryExtractRequest(BaseModel):
    user_query: str
    ai_response: str


class PriceAlertItem(BaseModel):
    id: int
    symbol: str
    stock_name: Optional[str] = None
    condition_type: str          # ABOVE / BELOW
    threshold: float


class PriceCheckRequest(BaseModel):
    user_id: str
    user_profile: str = "暂无"
    alerts: List[PriceAlertItem]
    already_pushed_ids: List[int] = []


def _sse(event: str, data: str) -> bytes:
    return f"event: {event}\ndata: {data}\n\n".encode("utf-8")


# ==================== 行情抓取（供预警判断） ====================
def _fetch_price_dict(code: str) -> dict:
    """从新浪抓结构化行情。失败返回 {}。"""
    try:
        code = str(code).replace("sh", "").replace("sz", "").strip()
        prefix = "sh" if code.startswith("6") else "sz"
        url = f"https://hq.sinajs.cn/list={prefix}{code}"
        r = requests.get(url, headers={"Referer": "https://finance.sina.com.cn/"}, timeout=5)
        r.encoding = "gbk"
        arr = r.text.split('="')[1].split('"')[0].split(",")
        if len(arr) < 32:
            return {}
        price = float(arr[3]) or float(arr[2])
        pre_close = float(arr[2])
        change_pct = (price - pre_close) / pre_close * 100 if pre_close > 0 else 0.0
        return {"name": arr[0], "price": price, "pre_close": pre_close, "change_pct": change_pct}
    except Exception:
        return {}


# ==================== 接口 1：流式对话（保持不变） ====================
@app.post("/internal/agent/stream")
async def agent_stream(req: AgentStreamRequest,
                       x_internal_token: Optional[str] = Header(None, alias="X-Internal-Token")):
    if x_internal_token != INTERNAL_TOKEN:
        raise HTTPException(status_code=403, detail="invalid token")

    relevant_history = []
    if req.history:
        history_texts = [m.content for m in req.history]
        tokenized_corpus = [jieba.lcut(text) for text in history_texts]
        if tokenized_corpus:
            bm25 = BM25Okapi(tokenized_corpus)
            query_tokens = jieba.lcut(req.user_query)
            top_n_indices = bm25.get_top_n(
                query_tokens, list(range(len(history_texts))), n=min(3, len(history_texts))
            )
            relevant_history = [req.history[i] for i in sorted(top_n_indices)]
            print(f"\n🔍 RAG 记忆检索：从 {len(req.history)} 条历史中筛选出最相关的 {len(relevant_history)} 条")

    langchain_history = [
        HumanMessage(content=m.content) if m.role == "user" else AIMessage(content=m.content)
        for m in relevant_history
    ]

    inputs = {
        "messages": langchain_history + [HumanMessage(content=req.user_query)],
        "user_context": req.user_memory,
        "retry_count": 0
    }

    async def event_gen():
        yield _sse("trace", json.dumps({"trace_id": req.trace_id}))
        total_tokens = 0
        try:
            async for event in multi_agent_app.astream_events(inputs, version="v2"):
                kind = event["event"]
                if kind == "on_chat_model_end":
                    output = event.get("data", {}).get("output")
                    if output and hasattr(output, "response_metadata"):
                        usage = output.response_metadata.get("token_usage", {})
                        if usage:
                            total_tokens += usage.get("total_tokens", 0)
                elif kind == "on_chat_model_stream":
                    if event.get("metadata", {}).get("langgraph_node") == "writer":
                        content = event["data"]["chunk"].content
                        if content:
                            yield _sse("chunk", json.dumps({"content": content}))
            yield _sse("metrics", json.dumps({"total_tokens": total_tokens}))
            yield _sse("done", json.dumps({"status": "success"}))
        except Exception as e:
            print(f"\n❌ 报错: {traceback.format_exc()}")
            yield _sse("error", json.dumps({"message": str(e)}))

    return StreamingResponse(event_gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ==================== 接口 2：记忆提取（保持不变） ====================
@app.post("/internal/agent/extract_memory")
async def extract_memory(req: MemoryExtractRequest,
                         x_internal_token: Optional[str] = Header(None, alias="X-Internal-Token")):
    if x_internal_token != INTERNAL_TOKEN:
        raise HTTPException(status_code=403, detail="invalid token")

    prompt = f"""
    你是一个记忆力超群的 AI 投资顾问。请分析以下对话，提取或更新用户的记忆。
    【用户问】: {req.user_query}
    【AI答】: {req.ai_response[:200]}

    【极其重要的规则】
    1. 冲突覆盖：如果用户的最新发言改变了他之前的状态（例如：以前重仓，现在清仓），你必须完全覆盖之前的旧状态。
    2. 提取事件：如果本次对话包含对未来的计划、明确的交易操作、或重要观点，请提取一句话存入 `episodic_event`。

    请严格输出以下 JSON 格式（只输出 JSON，不要解释）：
    {{
        "profile": "最新的风险偏好和风格",
        "portfolio": "最新的真实持仓情况",
        "watchlist": "目前关注的板块或事件",
        "episodic_event": "本次对话的重要事件总结"
    }}
    """
    try:
        llm = ChatOpenAI(api_key=API_KEY, base_url=BASE_URL, model=MODEL_FIXER, temperature=0)
        new_memory = (await llm.ainvoke([HumanMessage(content=prompt)])).content.strip()
        new_memory = new_memory.replace("```json", "").replace("```", "").strip()

        parsed = json.loads(new_memory)
        episodic_event = parsed.pop("episodic_event", "")
        memory_str = json.dumps(parsed, ensure_ascii=False)
    except Exception:
        memory_str = "{}"
        episodic_event = ""

    return {"memory": memory_str, "episodic_event": episodic_event}


# ==================== 接口 3：价格预警检查（新增） ====================
@app.post("/internal/agent/proactive/price_check")
async def price_check(req: PriceCheckRequest,
                      x_internal_token: Optional[str] = Header(None, alias="X-Internal-Token")):
    if x_internal_token != INTERNAL_TOKEN:
        raise HTTPException(status_code=403, detail="invalid token")

    if not req.alerts:
        return {"pushed": []}

    # ---------- 1. 批量查行情 ----------
    symbols = list({a.symbol for a in req.alerts})
    quotes = {sym: _fetch_price_dict(sym) for sym in symbols}

    # ---------- 2. 判断哪些触发（过滤已推过的） ----------
    already = set(req.already_pushed_ids)
    triggered = []
    for a in req.alerts:
        if a.id in already:
            continue
        q = quotes.get(a.symbol)
        if not q or not q.get("price"):
            continue
        price = q["price"]
        hit = (
            (a.condition_type == "ABOVE" and price >= a.threshold) or
            (a.condition_type == "BELOW" and price <= a.threshold)
        )
        if hit:
            triggered.append({
                "alert_id": a.id,
                "symbol": a.symbol,
                "stock_name": a.stock_name or q["name"],
                "price": price,
                "change_pct": round(q["change_pct"], 2),
                "condition_type": a.condition_type,
                "threshold": a.threshold,
            })

    if not triggered:
        return {"pushed": []}

    # ---------- 3. LLM 生成个性化推送文案 ----------
    items_for_llm = [
        {
            "alert_id": t["alert_id"],
            "股票": t["stock_name"],
            "代码": t["symbol"],
            "现价": t["price"],
            "涨跌幅": f"{t['change_pct']}%",
            "预警条件": f"{'涨破' if t['condition_type'] == 'ABOVE' else '跌破'} {t['threshold']}"
        }
        for t in triggered
    ]
    prompt = f"""你是用户的 AI 投资助手，现在要给用户推送价格预警。
【用户画像】: {req.user_profile}
【触发的预警】:
{json.dumps(items_for_llm, ensure_ascii=False, indent=2)}

请为每条预警生成一句简短、个性化、有温度的推送文案（30-80字），要求：
- 直接播报现价 + 触发条件
- 如果用户画像里有相关信息（如"关注茅台"/"想加仓"），自然带上一句建议或关心
- 禁止编造用户没说的话，禁止给明确买卖指令

输出 JSON 数组，每条含 alert_id 和 message：
[{{"alert_id": 12, "message": "茅台跌到 1698 了，你之前关注的加仓位置已经到，可以留意一下盘面。"}}]
只输出 JSON，不要 markdown。"""

    try:
        llm = ChatOpenAI(api_key=API_KEY, base_url=BASE_URL, model=MODEL_FIXER, temperature=0.3)
        raw = (await llm.ainvoke([HumanMessage(content=prompt)])).content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        messages_map = {m["alert_id"]: m["message"] for m in json.loads(raw)}
    except Exception as e:
        print(f"⚠️ 推送文案生成失败，用模板兜底: {e}")
        messages_map = {}

    # ---------- 4. 推送 ----------
    pushed = []
    for t in triggered:
        msg = messages_map.get(t["alert_id"]) or (
            f"【价格预警】{t['stock_name']}({t['symbol']}) 现价 {t['price']}，"
            f"{'已涨破' if t['condition_type'] == 'ABOVE' else '已跌破'} {t['threshold']}"
        )
        try:
            send_wechat_alert.invoke({"message": msg})
        except Exception as e:
            print(f"⚠️ 推送失败 alert_id={t['alert_id']}: {e}")
            continue
        pushed.append({"alert_id": t["alert_id"], "message": msg, "price": t["price"]})

    return {"pushed": pushed}