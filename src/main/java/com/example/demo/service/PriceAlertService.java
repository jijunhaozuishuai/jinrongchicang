package com.example.demo.service;

import com.example.demo.dto.PriceAlertItem;
import com.example.demo.dto.PriceAlertRequest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Mono;
import reactor.core.scheduler.Schedulers;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class PriceAlertService {
    private final JdbcTemplate jdbc;

    public PriceAlertService(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    private static final RowMapper<PriceAlertItem> MAPPER = (rs, i) -> new PriceAlertItem(
            rs.getLong("id"),
            rs.getString("symbol"),
            rs.getString("stock_name"),
            rs.getString("condition_type"),
            rs.getDouble("threshold")
    );

    /** 用户设新预警 */
    public Mono<Long> create(PriceAlertRequest req) {
        return Mono.fromCallable(() ->
                jdbc.queryForObject(
                        "INSERT INTO price_alerts (user_id, symbol, stock_name, condition_type, threshold) " +
                                "VALUES (?,?,?,?,?) RETURNING id",
                        Long.class,
                        req.userId(), req.symbol(), req.stockName(),
                        req.conditionType(), req.threshold())
        ).subscribeOn(Schedulers.boundedElastic());
    }

    /** 列出某用户所有活跃预警 */
    public Mono<List<PriceAlertItem>> listActive(String userId) {
        return Mono.fromCallable(() ->
                jdbc.query("SELECT * FROM price_alerts WHERE user_id=? AND status='active'",
                        MAPPER, userId)
        ).subscribeOn(Schedulers.boundedElastic());
    }

    /** 一次查询所有活跃预警，按 userId 分组（定时任务用） */
    public Map<String, List<PriceAlertItem>> listActiveGroupedByUser() {
        Map<String, List<PriceAlertItem>> grouped = new LinkedHashMap<>();
        jdbc.query("SELECT * FROM price_alerts WHERE status='active'", rs -> {
            String userId = rs.getString("user_id");
            PriceAlertItem item = new PriceAlertItem(
                    rs.getLong("id"),
                    rs.getString("symbol"),
                    rs.getString("stock_name"),
                    rs.getString("condition_type"),
                    rs.getDouble("threshold")
            );
            grouped.computeIfAbsent(userId, k -> new ArrayList<>()).add(item);
        });
        return grouped;
    }

    /** 标记为已触发 */
    public void markTriggered(Long alertId) {
        jdbc.update("UPDATE price_alerts SET status='triggered', triggered_at=NOW() WHERE id=?", alertId);
    }

    /** 用户取消 */
    public Mono<Void> cancel(String userId, Long id) {
        return Mono.fromRunnable(() ->
                jdbc.update("UPDATE price_alerts SET status='cancelled' WHERE id=? AND user_id=?", id, userId)
        ).subscribeOn(Schedulers.boundedElastic()).then();
    }
}