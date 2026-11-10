package com.example.demo.service;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Mono;
import reactor.core.scheduler.Schedulers;

@Service
public class FeedbackService {
    private final JdbcTemplate jdbc;
    public FeedbackService(JdbcTemplate jdbc) { this.jdbc = jdbc; }
    public Mono<Void> submit(String tid, String fb) {
        return Mono.fromRunnable(() -> jdbc.update("UPDATE system_logs SET feedback=? WHERE trace_id=?", fb, tid))
                   .subscribeOn(Schedulers.boundedElastic()).then();
    }
}
