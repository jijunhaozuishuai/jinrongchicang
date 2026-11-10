from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage
import operator

class AgentState(TypedDict):
    # 工作记忆：对话历史记录
    messages: Annotated[list[BaseMessage], operator.add]
    # 路由判断结果：quant / news / chat
    intent: str
    # 长期记忆与情景记忆：由 Java 端拼装后传入
    user_context: str
    # 重试次数
    retry_count: int