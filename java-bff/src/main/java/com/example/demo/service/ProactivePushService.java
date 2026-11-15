package com.example.demo.service;

import com.example.demo.client.AgentClient;
import com.example.demo.dto.PriceAlertItem;
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.time.LocalTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
public class ProactivePushService {
    private final PriceAlertService alertService;
    private final MemoryService memoryService;
    private final AgentClient agentClient;
    private final JdbcTemplate jdbc;

    private static final int SILENT_START_HOUR = 22;   // 22:00 后静默
    private static final int SILENT_END_HOUR = 8;      // 8:00 前静默
    private static final int DAILY_PUSH_LIMIT = 10;    // 单用户每天最多 10 条
    private static final int DEDUP_HOURS = 2;          // 2 小时内不重复推同一条

    public ProactivePushService(PriceAlertService alertService,
                                MemoryService memoryService,
                                AgentClient agentClient,
                                JdbcTemplate jdbc) {
        this.alertService = alertService;
        this.memoryService = memoryService;
        this.agentClient = agentClient;
        this.jdbc = jdbc;
    }

    /** 扫一轮所有活跃价格预警 */
    public void scanPriceAlerts() {
        Map<String, List<PriceAlertItem>> grouped = alertService.listActiveGroupedByUser();
        if (grouped.isEmpty()) return;

        for (Map.Entry<String, List<PriceAlertItem>> entry : grouped.entrySet()) {
            String userId = entry.getKey();
            List<PriceAlertItem> alerts = entry.getValue();

            if (inSilentHours()) {
                System.out.println("🔇 静默时段，跳过推送 userId=" + userId);
                continue;
            }
            int today = todayPushedCount(userId);
            if (today >= DAILY_PUSH_LIMIT) {
                System.out.println("📵 今日推送已达上限(" + today + ")，跳过 userId=" + userId);
                continue;
            }

            List<Long> alreadyPushed = recentPushedAlertIds(userId, DEDUP_HOURS);
            String profile = memoryService.loadMemory(userId).blockOptional().orElse("暂无");

            Map<String, Object> payload = new HashMap<>();
            payload.put("user_id", userId);
            payload.put("user_profile", profile);
            payload.put("alerts", alerts);
            payload.put("already_pushed_ids", alreadyPushed);

            final String uid = userId;
            agentClient.priceCheck(payload)
                    .doOnNext(resp -> handlePushed(uid, resp))
                    .doOnError(e -> System.err.println("❌ 价格检查失败 userId=" + uid + ": " + e.getMessage()))
                    .subscribe();
        }
    }

    private void handlePushed(String userId, JsonNode resp) {
        JsonNode pushed = resp.path("pushed");
        if (!pushed.isArray() || pushed.size() == 0) return;

        for (JsonNode p : pushed) {
            long alertId = p.path("alert_id").asLong();
            String msg = p.path("message").asText("");
            alertService.markTriggered(alertId);
            jdbc.update(
                    "INSERT INTO push_logs (user_id, event_type, event_key, content) VALUES (?,?,?,?)",
                    userId, "price_alert", "price_alert:" + alertId, msg);
        }
        System.out.println("✅ 已推送 " + pushed.size() + " 条价格预警 userId=" + userId);
    }

    private boolean inSilentHours() {
        int h = LocalTime.now().getHour();
        return h >= SILENT_START_HOUR || h < SILENT_END_HOUR;
    }

    private int todayPushedCount(String userId) {
        Integer c = jdbc.queryForObject(
                "SELECT COUNT(*) FROM push_logs WHERE user_id=? AND pushed_at >= CURRENT_DATE",
                Integer.class, userId);
        return c == null ? 0 : c;
    }

    private List<Long> recentPushedAlertIds(String userId, int hours) {
        return jdbc.query(
                "SELECT event_key FROM push_logs WHERE user_id=? AND event_type='price_alert' " +
                        "AND pushed_at >= NOW() - (? * INTERVAL '1 hour')",
                (rs, i) -> {
                    String key = rs.getString("event_key");
                    try { return Long.parseLong(key.split(":")[1]); } catch (Exception e) { return -1L; }
                }, userId, hours);
    }
}