package com.example.demo.dto;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

public record AgentStreamRequest(
    @JsonProperty("trace_id") String traceId,
    @JsonProperty("session_id") String sessionId,
    @JsonProperty("user_query") String userQuery,
    @JsonProperty("user_memory") String userMemory,
    List<HistoryMessage> history
) {
    public record HistoryMessage(String role, String content) {}
}
