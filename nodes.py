from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import Literal

from tools import (
    get_current_time, get_stock_quote, get_realtime_stock_price, query_financial_db,
    search_knowledge, get_user_portfolio, web_search_tool, python_repl, send_wechat_alert
)
from config import API_KEY, BASE_URL, MODEL_MAIN, MODEL_FIXER
from state import AgentState

# ============================================================
# 🔑 工具集常量：唯一数据源（Single Source of Truth）
# nodes.py 用它们 bind_tools；workflow.py 用它们建 ToolNode
# 以后新增/删除工具，只改这里一处即可
# ============================================================
QUANT_TOOLS = [query_financial_db, python_repl, get_current_time]
NEWS_TOOLS  = [get_stock_quote, get_realtime_stock_price, web_search_tool, get_current_time, send_wechat_alert]
CHAT_TOOLS  = [search_knowledge, get_user_portfolio, get_current_time]


class RouteQuery(BaseModel):
    intent: Literal["quant", "news", "chat"] = Field(
        default="chat",
        description="quant: 财务数据/计算/查库; news: 实时行情/新闻/宏观; chat: 闲聊/私人持仓/定性分析"
    )


def router_node(state: AgentState):
    query = state["messages"][-1].content
    if any(k in query for k in ["价格", "股价", "行情", "多少", "走势", "大盘"]):
        return {"intent": "news"}

    llm = ChatOpenAI(api_key=API_KEY, base_url=BASE_URL, model=MODEL_FIXER, temperature=0)
    structured_llm = llm.with_structured_output(RouteQuery)
    prompt = ChatPromptTemplate.from_messages([
        ("system", "意图分类。涉及股票、新闻输出 news；财务数据输出 quant；其余 chat。"),
        ("human", "{query}")
    ])
    try:
        res = structured_llm.invoke(prompt.format(query=query))
        return {"intent": res.intent if res.intent else "chat"}
    except Exception:
        return {"intent": "chat"}


llm_main = ChatOpenAI(api_key=API_KEY, base_url=BASE_URL, model=MODEL_MAIN, temperature=0)


def quant_node(state: AgentState):
    # 用常量绑定工具，和 workflow 的 ToolNode(QUANT_TOOLS) 天然一致
    llm_with_tools = llm_main.bind_tools(QUANT_TOOLS)
    system = SystemMessage(content="你是财务数据专家。查库时注意列名用双引号。算数必须调 python_repl。")
    return {"messages": [llm_with_tools.invoke([system] + state["messages"])]}


def news_node(state: AgentState):
    llm_with_tools = llm_main.bind_tools(NEWS_TOOLS)
    system = SystemMessage(content="""你是市场资讯专家。
用户问股价，你【必须】立刻调用 `get_stock_quote` 工具！绝对不许说自己查不到！
如果不知道代码，茅台传 600519，伊利传 600887，平安银行传 000001。查完直接播报。""")
    return {"messages": [llm_with_tools.invoke([system] + state["messages"])]}


def chat_node(state: AgentState):
    context = state.get("user_context", "暂无")
    llm_with_tools = llm_main.bind_tools(CHAT_TOOLS)
    system = SystemMessage(
        content=f"你是私人投资顾问。涉及风险、战略用 search_knowledge。涉及持仓用 get_user_portfolio。\n背景：{context}")
    return {"messages": [llm_with_tools.invoke([system] + state["messages"])]}


def writer_node(state: AgentState):
    context = state.get("user_context", "暂无")
    tool_info = ""
    for msg in state["messages"]:
        if isinstance(msg, ToolMessage):
            tool_info += f"\n工具 {msg.name} 查询到的真实数据：{msg.content}"

    system_content = f"你是一个专业的A股首席分析师。请参考背景：{context}。请用专业、客观的语气回答用户问题。"
    if tool_info:
        system_content += f"\n\n【注意：以下是刚刚查到的真实数据，你必须直接、原原本本地播报给用户】：\n{tool_info}"

    prompt = SystemMessage(content=system_content)

    clean_messages = []
    for msg in state["messages"]:
        if isinstance(msg, HumanMessage):
            clean_messages.append(msg)
        elif isinstance(msg, AIMessage) and not getattr(msg, "tool_calls", None):
            if "查不到" not in msg.content and "无法获取" not in msg.content:
                clean_messages.append(msg)

    if not clean_messages:
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage):
                clean_messages.append(msg)
                break

    return {"messages": [llm_main.invoke([prompt] + clean_messages)]}


def route_decision(state: AgentState):
    intent = state.get("intent", "chat")
    if intent == "quant":
        return "quant_node"
    elif intent == "news":
        return "news_node"
    return "chat_node"