package com.example.demo.service;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

@Service
public class MonitorService {
    private final JdbcTemplate jdbc;
    public MonitorService(JdbcTemplate jdbc) { this.jdbc = jdbc; }
    
    @Async("monitorExecutor")
    public void logAsync(String traceId, String sid, String query, String tool, long timeMs, int tokens, String status, String err) {
        jdbc.update("INSERT INTO system_logs (trace_id, session_id, user_query, tool_used, execution_time_ms, total_tokens, estimated_cost_yuan, status, error_msg) VALUES (?,?,?,?,?,?,?,?,?)",
            traceId, sid, query, tool, timeMs, tokens, (tokens/1000.0)*0.02, status, err);
    }
}
