import os
import shutil
import pickle
import sqlite3
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from config import API_KEY, BASE_URL, MODEL_EMBEDDING, PARENT_STORE_PATH, FAISS_INDEX_PATH, BM25_INDEX_PATH

TARGET_FILE = "data/投资知识库.md"
SQLITE_DB_PATH = os.path.join(PARENT_STORE_PATH, "parent_store.db")


def build():
    print("⏳ 开始构建向量知识库...")
    if not os.path.exists(TARGET_FILE):
        print(f"❌ 错误：找不到源文件 {TARGET_FILE}")
        return

    # 清理旧数据
    for path in [PARENT_STORE_PATH, FAISS_INDEX_PATH, BM25_INDEX_PATH]:
        if os.path.exists(path):
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)

    os.makedirs(PARENT_STORE_PATH, exist_ok=True)

    with open(TARGET_FILE, "r", encoding="utf-8") as f:
        text = f.read()

    embeddings = OpenAIEmbeddings(
        api_key=API_KEY, base_url=BASE_URL, model=MODEL_EMBEDDING,
        check_embedding_ctx_length=False, chunk_size=10
    )

    parent_splitter = RecursiveCharacterTextSplitter(
        separators=["\n# ", "\n## ", "\n\n"], chunk_size=2000, chunk_overlap=200, keep_separator=True
    )
    child_splitter = RecursiveCharacterTextSplitter(
        separators=["\n### ", "\n## ", "\n# ", "\n\n"], chunk_size=400, chunk_overlap=50, keep_separator=True
    )

    print("正在切分文档并构建父子映射...")
    parent_docs = parent_splitter.split_documents([Document(page_content=text)])

    child_docs = []
    conn = sqlite3.connect(SQLITE_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS parent_docs (doc_id TEXT PRIMARY KEY, content TEXT)")

    for i, p_doc in enumerate(parent_docs):
        parent_id = f"parent_{i}"
        # 父块存入 SQLite
        cursor.execute("INSERT OR REPLACE INTO parent_docs (doc_id, content) VALUES (?, ?)",
                       (parent_id, p_doc.page_content))

        # 子块绑定父块 ID
        sub_docs = child_splitter.split_documents([p_doc])
        for s_doc in sub_docs:
            s_doc.metadata["parent_id"] = parent_id
            child_docs.append(s_doc)

    conn.commit()
    conn.close()

    print(f"✅ 切分完毕：{len(parent_docs)} 个父块，{len(child_docs)} 个子块。")

    print("正在生成 FAISS 向量...")
    vectorstore = FAISS.from_documents(child_docs, embeddings)
    vectorstore.save_local(FAISS_INDEX_PATH)

    print("正在构建 BM25 索引...")
    with open(BM25_INDEX_PATH, "wb") as f:
        pickle.dump(child_docs, f)

    print("🎉 大功告成！父块存 SQLite，子块存 FAISS/BM25。")


if __name__ == "__main__":
    build()