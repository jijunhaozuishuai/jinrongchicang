package com.example.demo.service;
import com.example.demo.dto.AgentStreamRequest.HistoryMessage;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Mono;
import reactor.core.scheduler.Schedulers;
import java.util.ArrayList; import java.util.Collections; import java.util.List;

@Service
public class HistoryService {
    private final JdbcTemplate jdbc;
    public HistoryService(JdbcTemplate jdbc) { this.jdbc = jdbc; }
    public Mono<List<HistoryMessage>> loadHistory(String sid, int limit) {
        return Mono.fromCallable(() -> {
            List<HistoryMessage> list = jdbc.query("SELECT role, content FROM chat_history WHERE session_id = ? ORDER BY created_at DESC LIMIT ?",
                (rs, i) -> new HistoryMessage(rs.getString("role"), rs.getString("content")), sid, limit);
            List<HistoryMessage> rev = new ArrayList<>(list); Collections.reverse(rev); return rev;
        }).subscribeOn(Schedulers.boundedElastic());
    }
    public void saveMessage(String sid, String role, String content) {
        Schedulers.boundedElastic().schedule(() -> jdbc.update("INSERT INTO chat_history (session_id, role, content) VALUES (?,?,?)", sid, role, content));
    }
}
