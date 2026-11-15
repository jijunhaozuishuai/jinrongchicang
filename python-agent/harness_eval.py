import os
import json
import asyncio
import config
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

# 1. 适配最新的 LangGraph 多智能体架构
from workflow import app as agent_executor

# 2. 配置 Langfuse 环境变量
os.environ["LANGFUSE_PUBLIC_KEY"] = config.LANGFUSE_PUBLIC_KEY
os.environ["LANGFUSE_SECRET_KEY"] = config.LANGFUSE_SECRET_KEY
os.environ["LANGFUSE_HOST"] = config.LANGFUSE_HOST

from langfuse.langchain import CallbackHandler
langfuse_handler = CallbackHandler()

# 3. 初始化评审大模型
judge_llm = ChatOpenAI(
    api_key=config.API_KEY,
    base_url=config.BASE_URL,
    model=config.MODEL_MAIN,
    temperature=0
)

# 4. 读取测试集
try:
    with open("golden_test_set.json", "r", encoding="utf-8") as f:
        test_cases = json.load(f)
except FileNotFoundError:
    print("❌ 找不到 golden_test_set.json，请确保该文件在同级目录下！")
    exit(1)

JUDGE_PROMPT_TEMPLATE = """
你是一个严格的 AI 质量评审专家。请根据【标准答案】和【AI回答】，对AI回答的"语义准确度"进行1-5分打分。
【用户问题】: {query}
【标准答案】: {expected}
【AI回答】: {answer}
评分标准：
- 5分：完美回答，包含了核心数据。允许单位换算。
- 3-4分：包含核心点，但不够精确。
- 1-2分：答非所问或编造数据。
请严格按以下 JSON 格式输出（不要输出其他内容）：{{"score": 数字, "reason": "简短理由"}}
"""

async def run_harness():
    print("⚖️ 企业级混合评测 Harness 启动 [Langfuse 追踪已开启]")
    total_cases = len(test_cases)
    route_pass, hard_assert_pass, total_judge_score = 0, 0, 0

    for i, case in enumerate(test_cases, 1):
        print(f"\n▶ [用例 {i}] {case['query']}")
        called_tools, final_output = [], ""

        try:
            # 运行 LangGraph 并追踪事件
            async for event in agent_executor.astream_events(
                    {"messages": [HumanMessage(content=case["query"])]},
                    version="v2", config={"callbacks": [langfuse_handler], "metadata": {"test_case_id": i}}
            ):
                if event["event"] == "on_tool_start":
                    called_tools.append(event["name"])
                elif event["event"] == "on_chat_model_stream":
                    # 只抓取最终 writer 节点的输出
                    if event.get("metadata", {}).get("langgraph_node") == "writer":
                        content = event["data"]["chunk"].content
                        if content:
                            final_output += content
        except Exception as e:
            print(f"  ❌ 执行异常: {e}")
            continue

        # 1. 评估工具路由 (正确调用/禁止调用)
        is_route_pass = True
        if case.get("required_tool") and case["required_tool"] not in called_tools:
            is_route_pass = False
        if case.get("forbidden_tool") and case["forbidden_tool"] in called_tools:
            is_route_pass = False
        if is_route_pass:
            route_pass += 1

        # 2. 评估事实命中率 (硬匹配标准答案中的关键词/数字)
        clean_out = final_output.replace(",", "").replace("，", "")
        hit_any = any(exp.replace(",", "").replace("，", "") in clean_out for exp in case["expected"])
        if hit_any:
            hard_assert_pass += 1

        # 3. 大模型语义打分
        judge_prompt = JUDGE_PROMPT_TEMPLATE.format(
            query=case["query"],
            expected=" 或 ".join(case["expected"]),
            answer=final_output
        )
        try:
            judge_json = json.loads(judge_llm.invoke([HumanMessage(content=judge_prompt)]).content)
            score, reason = judge_json.get("score", 0), judge_json.get("reason", "")
            total_judge_score += score
            print(f"  └── 评分: {score}/5 | 理由: {reason}")
        except Exception as e: 
            print(f"  └── 打分异常: {e}")

    print("\n📊 最终诊断报告")
    print(f"工具路由准确率: {route_pass}/{total_cases} | 事实命中率: {hard_assert_pass}/{total_cases} | 语义平均分: {total_judge_score/total_cases:.2f}")

if __name__ == "__main__":
    asyncio.run(run_harness())