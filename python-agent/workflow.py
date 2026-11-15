from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition
from state import AgentState
from nodes import (
    router_node, quant_node, news_node, chat_node, writer_node, route_decision,
    QUANT_TOOLS, NEWS_TOOLS, CHAT_TOOLS   # 🔑 从 nodes 导入，保证工具集唯一
)

# ============================================================
# 1. 循环上限工厂：给 tools_condition 套上"最多 N 轮"的保护
# ============================================================
def make_tools_condition(max_tool_rounds: int = 5):
    """
    生成一个带循环上限的 tools_condition。
    - 计数方式：messages 里带 tool_calls 的 AIMessage 条数 = 已经发生的工具调用轮次
    - 达到上限：强制返回 "__end__"，避免 LLM 抽风无限循环烧 token
    - 未达上限：走原生 tools_condition（"tools" 或 "__end__"）
    """
    def _cond(state):
        rounds = sum(1 for m in state["messages"] if getattr(m, "tool_calls", None))
        if rounds >= max_tool_rounds:
            print(f"⚠️ 工具调用达到上限 {max_tool_rounds} 轮，强制结束转 writer")
            return "__end__"
        return tools_condition(state)
    return _cond


# ============================================================
# 2. 每个专家独立 ToolNode，工具集从 nodes 导入的常量构建
# ============================================================
quant_tool_node = ToolNode(QUANT_TOOLS)
news_tool_node  = ToolNode(NEWS_TOOLS)
chat_tool_node  = ToolNode(CHAT_TOOLS)

workflow = StateGraph(AgentState)

# ---------- 3. 注册节点 ----------
workflow.add_node("router", router_node)
workflow.add_node("quant_node", quant_node)
workflow.add_node("news_node", news_node)
workflow.add_node("chat_node", chat_node)
workflow.add_node("writer", writer_node)
workflow.add_node("quant_tools", quant_tool_node)
workflow.add_node("news_tools",  news_tool_node)
workflow.add_node("chat_tools",  chat_tool_node)

# ---------- 4. 入口 + 意图路由 ----------
workflow.set_entry_point("router")
workflow.add_conditional_edges(
    "router", route_decision,
    {"quant_node": "quant_node", "news_node": "news_node", "chat_node": "chat_node"}
)

# ---------- 5. 每个专家：带循环上限的 tools_condition ----------
MAX_TOOL_ROUNDS = 5   # 全局统一上限，可按需调整

workflow.add_conditional_edges(
    "quant_node", make_tools_condition(MAX_TOOL_ROUNDS),
    {"tools": "quant_tools", "__end__": "writer"}
)
workflow.add_conditional_edges(
    "news_node", make_tools_condition(MAX_TOOL_ROUNDS),
    {"tools": "news_tools", "__end__": "writer"}
)
workflow.add_conditional_edges(
    "chat_node", make_tools_condition(MAX_TOOL_ROUNDS),
    {"tools": "chat_tools", "__end__": "writer"}
)

# ---------- 6. 工具执行完，回到"发起方"专家继续生成 ----------
workflow.add_edge("quant_tools", "quant_node")
workflow.add_edge("news_tools",  "news_node")
workflow.add_edge("chat_tools",  "chat_node")

# ---------- 7. 收尾 ----------
workflow.add_edge("writer", END)

app = workflow.compile()