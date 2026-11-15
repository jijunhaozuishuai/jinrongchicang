package com.example.demo.service;

import com.example.demo.client.AgentClient;
import com.example.demo.dto.AgentStreamRequest;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.util.Collections;
import java.util.UUID;

@Component
public class ScheduledTasks {
    private final AgentClient agentClient;
    private final ProactivePushService proactivePushService;

    public ScheduledTasks(AgentClient agentClient, ProactivePushService proactivePushService) {
        this.agentClient = agentClient;
        this.proactivePushService = proactivePushService;
    }

    // 每日早报（保持原样）
    @Scheduled(cron = "0 30 8 * * ?")
    public void generateMorningBriefing() {
        System.out.println("⏰ 【定时任务触发】开始生成今日 A 股早报...");
        String prompt = "请调用工具查询大盘行情，并总结今天A股开盘前需要关注的三个核心看点。";
        AgentStreamRequest req = new AgentStreamRequest(
                UUID.randomUUID().toString().substring(0, 8),
                "daily_briefing_system",
                prompt,
                "用户风险偏好: 稳健型，主做科技股。",
                Collections.emptyList()
        );
        agentClient.streamChat(req)
                .doOnNext(event -> { /* 可选：推 WebSocket 或落库 */ })
                .doFinally(signal -> System.out.println("\n✅ 今日早报生成完毕。"))
                .subscribe();
    }

    // 交易时段每 5 分钟扫价格预警（9:30-11:30, 13:00-15:00 主体）
    @Scheduled(cron = "0 */5 9-11,13-14 * * MON-FRI")
    public void scanPriceAlertsDuringTrading() {
        System.out.println("🔍 [价格预警扫描] " + java.time.LocalDateTime.now());
        proactivePushService.scanPriceAlerts();
    }

    // 收盘后补一次（15:00 整）
    @Scheduled(cron = "0 0 15 * * MON-FRI")
    public void scanPriceAlertsAtClose() {
        System.out.println("🔍 [价格预警扫描·收盘] " + java.time.LocalDateTime.now());
        proactivePushService.scanPriceAlerts();
    }
}