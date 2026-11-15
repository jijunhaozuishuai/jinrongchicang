package com.example.demo.service;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Mono;
import reactor.core.scheduler.Schedulers;

@Service
public class MemoryService {
    private final JdbcTemplate jdbc;

    public MemoryService(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public Mono<String> loadMemory(String uid) {
        return Mono.fromCallable(() -> {
            try {
                var list = jdbc.queryForList("SELECT memory_content FROM user_memories WHERE user_id=?", String.class, uid);
                return list.isEmpty() ? "暂无画像" : list.get(0);
            } catch (Exception e) {
                return "暂无画像";
            }
        }).subscribeOn(Schedulers.boundedElastic());
    }

    public Mono<String> loadEpisodicMemory(String uid) {
        return Mono.fromCallable(() -> {
            try {
                var list = jdbc.queryForList("SELECT event_summary FROM episodic_memory WHERE user_id=? ORDER BY created_at DESC LIMIT 3", String.class, uid);
                return list.isEmpty() ? "暂无历史事件" : String.join("；", list);
            } catch (Exception e) {
                return "暂无历史事件";
            }
        }).subscribeOn(Schedulers.boundedElastic());
    }

    public Mono<Void> updateMemory(String uid, String mem) {
        return Mono.fromRunnable(() -> jdbc.update("INSERT INTO user_memories (user_id, memory_content) VALUES (?,?) ON CONFLICT (user_id) DO UPDATE SET memory_content=EXCLUDED.memory_content", uid, mem))
                .subscribeOn(Schedulers.boundedElastic()).then();
    }

    public Mono<Void> saveEpisodicMemory(String uid, String eventSummary) {
        return Mono.fromRunnable(() -> jdbc.update("INSERT INTO episodic_memory (user_id, event_summary) VALUES (?,?)", uid, eventSummary))
                .subscribeOn(Schedulers.boundedElastic()).then();
    }
}