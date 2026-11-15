import os
import pickle
import requests
import sqlite3
import jieba
from datetime import datetime
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers import EnsembleRetriever
from langchain_core.tools import tool
from langchain_experimental.tools import PythonREPLTool
from langchain_community.tools.tavily_search import TavilySearchResults

# 导入配置（包含真实的 SERVERCHAN_SENDKEY）
from config import (
    API_KEY, BASE_URL, PARENT_STORE_PATH, FAISS_INDEX_PATH, BM25_INDEX_PATH,
    MODEL_EMBEDDING, TAVILY_API_KEY, SERVERCHAN_SENDKEY
)
from database import get_db_conn

# ================= 初始化基础工具 =================
python_repl = PythonREPLTool()
os.environ["TAVILY_API_KEY"] = TAVILY_API_KEY
web_search_tool = TavilySearchResults(max_results=3)

# ================= 初始化混合检索器 =================
print("正在加载 FAISS + BM25 混合检索库...")
embeddings = OpenAIEmbeddings(
    api_key=API_KEY, base_url=BASE_URL, model=MODEL_EMBEDDING,
    check_embedding_ctx_length=False, chunk_size=10
)

try:
    vectorstore = FAISS.load_local(FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
    faiss_retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

    with open(BM25_INDEX_PATH, "rb") as f:
        sub_docs = pickle.load(f)

    bm25_retriever = BM25Retriever.from_documents(sub_docs, preprocess_func=jieba.lcut)
    bm25_retriever.k = 3

    ensemble_retriever = EnsembleRetriever(retrievers=[bm25_retriever, faiss_retriever], weights=[0.4, 0.6])
    print("✅ 混合检索库加载完成！")
except Exception as e:
    print(f"⚠️ 向量库加载失败，请确保已运行 build_kb.py: {e}")
    ensemble_retriever = None


# ================= 工具定义 =================

@tool
def get_current_time() -> str:
    """【时间工具】获取当前的系统时间和日期。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@tool
def get_stock_quote(code: str) -> str:
    """【实时行情】查询单只 A 股的最新实时价格及相关详细数据。code 是 6 位代码，如 600519。"""
    try:
        # 兼容带后缀或不带后缀的代码
        code = str(code).replace("sh", "").replace("sz", "").strip()
        url = f"https://hq.sinajs.cn/list=sh{code}" if code.startswith('6') else f"https://hq.sinajs.cn/list=sz{code}"

        response = requests.get(url, headers={"Referer": "https://finance.sina.com.cn/"}, timeout=5)
        response.encoding = 'gbk'
        data_list = response.text.split('="')[1].split('"')[0].split(',')

        if len(data_list) < 32:
            return f"未查询到代码为 {code} 的有效行情数据。"

        # 获取字段
        name = data_list[0]
        open_p = float(data_list[1])
        pre_close = float(data_list[2])
        price = float(data_list[3])
        high = float(data_list[4])
        low = float(data_list[5])
        volume = float(data_list[8])
        amount = float(data_list[9])
        date = data_list[30]
        time = data_list[31]

        # 如果当前是停牌状态，价格可能为 0
        if price == 0:
            price = pre_close

        # 计算涨跌额与涨跌幅
        change = 0.0
        change_pct = 0.0
        if pre_close > 0:
            change = price - pre_close
            change_pct = (change / pre_close) * 100

        # 单位换算
        volume_hand = volume / 100  # 股换算为手
        amount_wan = amount / 10000  # 元换算为万元

        result = (f"股票名称: {name} ({code})\n"
                  f"最新价: {price:.2f} 元\n"
                  f"涨跌额: {change:+.2f} 元\n"
                  f"涨跌幅: {change_pct:+.2f}%\n"
                  f"今开: {open_p:.2f} 元 | 昨收: {pre_close:.2f} 元\n"
                  f"最高: {high:.2f} 元 | 最低: {low:.2f} 元\n"
                  f"成交量: {volume_hand:.0f} 手 | 成交额: {amount_wan:.2f} 万元\n"
                  f"行情时间: {date} {time}")
        return result
    except Exception as e:
        return f"行情获取失败: {e}"


@tool
def get_realtime_stock_price(symbol: str) -> str:
    """【实时行情备用】查询单只 A 股的最新实时价格。参数 symbol 必须是 6 位数字代码。"""
    return get_stock_quote.invoke({"code": symbol})


@tool
def query_financial_db(sql_query: str) -> str:
    """【定量查询】查具体财务数字。表名 financial_data，列名：'营业总收入', '归母净利润', '报告期'。"""
    if not sql_query.strip().upper().startswith("SELECT"):
        return "错误：只允许 SELECT 查询。"
    try:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql_query)
                return str(cur.fetchall())
    except Exception as e:
        return f"数据库错误: {str(e)}"


@tool
def search_knowledge(query: str) -> str:
    """【定性查询】查询公司背景、战略、风险等纯文本信息时调用。"""
    if not ensemble_retriever:
        return "知识库未加载。"
    try:
        child_docs = ensemble_retriever.invoke(query)
        parent_ids = [doc.metadata.get("parent_id") for doc in child_docs if "parent_id" in doc.metadata]
        if not parent_ids:
            return "没有找到相关的父文档。"
        db_path = os.path.join(PARENT_STORE_PATH, "parent_store.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        unique_ids = list(set(parent_ids))
        placeholders = ','.join(['?'] * len(unique_ids))
        cursor.execute(f"SELECT content FROM parent_docs WHERE doc_id IN ({placeholders})", unique_ids)
        results = cursor.fetchall()
        conn.close()
        return "\n\n---\n\n".join([row[0] for row in results])
    except Exception as e:
        return f"检索失败: {e}"


@tool
def get_user_portfolio(user_id: str) -> str:
    """【私人资产】查询用户当前的持仓成本、股数和比例。"""
    return "用户当前重仓持有贵州茅台(600519) 100股，成本价1600元，仓位占比80%。另外持有少量现金。"


@tool
def send_wechat_alert(message: str) -> str:
    """【主动推送】给用户发送真实的微信通知。当用户明确要求'发给我/提醒我'，或触发价格预警时调用。"""
    if not SERVERCHAN_SENDKEY or SERVERCHAN_SENDKEY.startswith("SCTxxx"):
        print(f"\n🚨 【微信未配置】模拟消息内容: {message}")
        return "推送失败：请在 config.py 中配置真实的 SERVERCHAN_SENDKEY"

    # 提取标题（Server酱要求标题不能过长，且不能有换行）
    title = message.split("\n")[0][:32] if "\n" in message else message[:32]
    desp = message if len(message) > 32 else ""

    url = f"https://sctapi.ftqq.com/{SERVERCHAN_SENDKEY}.send"
    payload = {"title": title, "desp": desp}

    try:
        resp = requests.post(url, json=payload, timeout=10)
        res_json = resp.json()
        if res_json.get("code") == 0:
            print(f"\n✅ 【真实微信推送成功】内容: {title}")
            return f"✅ 微信推送成功：{title}"
        else:
            print(f"\n❌ 【微信推送失败】原因: {res_json.get('message')}")
            return f"❌ 微信推送失败：{res_json.get('message')}"
    except Exception as e:
        print(f"\n❌ 【微信推送异常】: {str(e)}")
        return f"❌ 微信推送异常：{str(e)}"