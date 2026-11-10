import psycopg2
from psycopg2 import pool
from contextlib import contextmanager
from config import DB_CONFIG

try:
    db_pool = pool.ThreadedConnectionPool(1, 20, **DB_CONFIG)
    print("✅ 【Python端】PostgreSQL 数据库连接池初始化成功！")
except Exception as e:
    print(f"❌ 【Python端】数据库连接失败: {e}")
    db_pool = None

@contextmanager
def get_db_conn():
    if not db_pool:
        raise Exception("数据库连接池未初始化")
    conn = db_pool.getconn()
    try:
        yield conn
    finally:
        db_pool.putconn(conn)