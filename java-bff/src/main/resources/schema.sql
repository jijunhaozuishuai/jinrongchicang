CREATE TABLE IF NOT EXISTS chat_history (
    id BIGSERIAL PRIMARY KEY, session_id VARCHAR(64) NOT NULL,
    role VARCHAR(16) NOT NULL, content TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_chat_history_session ON chat_history(session_id, created_at);
CREATE TABLE IF NOT EXISTS system_logs (
    id BIGSERIAL PRIMARY KEY, trace_id VARCHAR(64) NOT NULL UNIQUE, session_id VARCHAR(64),
    user_query TEXT, tool_used TEXT, execution_time_ms BIGINT, total_tokens INT,
    estimated_cost_yuan NUMERIC(12,6), status VARCHAR(16), error_msg TEXT, feedback VARCHAR(16), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS user_memories (
    user_id VARCHAR(64) PRIMARY KEY, memory_content TEXT NOT NULL, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
