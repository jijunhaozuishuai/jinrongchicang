import os
from dotenv import load_dotenv

# 自动加载当前目录下的 .env 文件
load_dotenv()

# ================= 模型配置 =================
# 全部从环境变量读取，如果读不到，提供一个安全的默认值
API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
BASE_URL = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

MODEL_MAIN = os.getenv("MODEL_MAIN", "qwen3.8-max-0902")
MODEL_FIXER = os.getenv("MODEL_FIXER", "qwen3.8-max-0902")
MODEL_EMBEDDING = os.getenv("MODEL_EMBEDDING", "text-embedding-v2")

# ================= 内部令牌与三方工具 =================
INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "change-me-in-prod")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# ================= 真实微信推送配置 =================
# 去 https://sct.ftqq.com 微信扫码登录获取，填在 .env 里，不要写在这里！
SERVERCHAN_SENDKEY = os.getenv("SERVERCHAN_SENDKEY", "")

# ================= 数据库配置 =================
# 同样全部从 .env 读取
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "finance_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "123456")

DB_CONFIG = {
    "host": DB_HOST,
    "port": DB_PORT,
    "database": DB_NAME,
    "user": DB_USER,
    "password": DB_PASSWORD
}

# ================= 向量库与检索路径 =================
PARENT_STORE_PATH = os.getenv("PARENT_STORE_PATH", "./storage/parent_docstore")
FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", "./storage/faiss_index")
BM25_INDEX_PATH = os.getenv("BM25_INDEX_PATH", "./storage/bm25_index.pkl")