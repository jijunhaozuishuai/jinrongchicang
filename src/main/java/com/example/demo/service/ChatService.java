package com.example.demo.service;

import com.example.demo.client.AgentClient;
import com.example.demo.dto.AgentStreamRequest;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.data.redis.core.ReactiveStringRedisTemplate;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import java.time.Duration;
import java.util.Map;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

@Service
public class ChatService {
    private final AgentClient agentClient;
    private final HistoryService historyService;
    private final MemoryService memoryService;
    private final MonitorService monitorService;
    private final ReactiveStringRedisTemplate redis;
    private final ObjectMapper objectMapper;

    public ChatService(AgentClient agentClient, HistoryService historyService, MemoryService memoryService, MonitorService monitorService, ReactiveStringRedisTemplate redis, ObjectMapper objectMapper) {
        this.agentClient = agentClient; this.historyService = historyService; this.memoryService = memoryService;
        this.monitorService = monitorService; this.redis = redis; this.objectMapper = objectMapper;
    }

    public Flux<ServerSentEvent<String>> chat(String sessionId, String userQuery, String traceId) {
        // ⚠️ 注意：缓存键不含记忆版本。用户记忆变更后，相同 query 仍会命中旧缓存。
        // 如需严格一致，建议在 cacheKey 里加入 memory 的 hash（如 memoryService.loadMemory 的摘要）。
        String cacheKey = "chat_cache:" + sessionId + ":" + userQuery;
        long startTime = System.currentTimeMillis();

        return redis.opsForValue().get(cacheKey)
                .flatMapMany(cacheHit -> {
                    monitorService.logAsync(traceId, sessionId, userQuery, "CACHE", System.currentTimeMillis() - startTime, 0, "success", null);
                    historyService.saveMessage(sessionId, "user", userQuery);
                    historyService.saveMessage(sessionId, "ai", cacheHit);
                    return Flux.just(createSse("trace", "{\"trace_id\":\"" + traceId + "\"}"),
                            createSse("chunk", "{\"content\":\"" + cacheHit.replace("\"", "\\\"") + "\"}"),
                            createSse("done", "{\"status\":\"success\"}"));
                })
                .switchIfEmpty(Flux.defer(() -> {
                    return Mono.zip(
                            historyService.loadHistory(sessionId, 10),
                            memoryService.loadMemory(sessionId),
                            memoryService.loadEpisodicMemory(sessionId)
                    ).flatMapMany(tuple -> {
                        String combinedMemory = "【长期画像】" + tuple.getT2() + "\n【近期事件】" + tuple.getT3();
                        AgentStreamRequest req = new AgentStreamRequest(traceId, sessionId, userQuery, combinedMemory, tuple.getT1());

                        // ⚠️ 注意：这里传的是 sessionId，但 MemoryService 底层查询的是 user_id。
                        // 若业务上 sessionId ≠ 用户ID（多会话同用户），记忆会隔离到每个会话，无法跨会话保留。
                        // 请确认业务语义：若确实要按"用户"存记忆，应显式传入真正的 userId。
                        String oldMemoryForExtract = tuple.getT2();

                        StringBuilder fullAnswer = new StringBuilder();
                        AtomicInteger tokens = new AtomicInteger(0);
                        AtomicBoolean isError = new AtomicBoolean(false);

                        return agentClient.streamChat(req)
                                .doOnNext(evt -> {
                                    if ("chunk".equals(evt.event()) && evt.data() != null) {
                                        try {
                                            String content = objectMapper.readTree(evt.data()).path("content").asText("");
                                            fullAnswer.append(content);
                                        } catch (Exception ignored) {}
                                    } else if ("metrics".equals(evt.event())) {
                                        try { tokens.set(objectMapper.readTree(evt.data()).path("total_tokens").asInt(0)); } catch (Exception ignored) {}
                                    } else if ("error".equals(evt.event())) {
                                        isError.set(true);
                                    }
                                })
                                // doFinally：客户端断开也保证保存/记忆更新
                                .doFinally(signal -> {
                                    long cost = System.currentTimeMillis() - startTime;
                                    if (!isError.get() && fullAnswer.length() > 0) {
                                        historyService.saveMessage(sessionId, "user", userQuery);
                                        historyService.saveMessage(sessionId, "ai", fullAnswer.toString());
                                        redis.opsForValue().set(cacheKey, fullAnswer.toString(), Duration.ofSeconds(300)).subscribe();
                                        monitorService.logAsync(traceId, sessionId, userQuery, "AGENT", cost, tokens.get(), "success", null);

                                        // 传旧记忆 + 解析冲突消解结果
                                        agentClient.extractMemory(Map.of(
                                                        "user_query", userQuery,
                                                        "ai_response", fullAnswer.toString(),
                                                        "old_memory", oldMemoryForExtract
                                                ))
                                                .doOnError(e -> System.err.println("❌ 记忆提取接口异常: " + e.getMessage()))
                                                .subscribe(res -> {
                                                    try {
                                                        JsonNode root      = objectMapper.readTree(res);
                                                        String mem         = root.path("memory").asText("");
                                                        String episodic    = root.path("episodic_event").asText("");
                                                        JsonNode changed   = root.path("changed_fields");
                                                        JsonNode conflicts = root.path("conflicts");

                                                        // 只有字段真变了才落库（changed_fields 由 Python 端自动计算，可靠）
                                                        boolean hasChange = changed.isArray() && changed.size() > 0;
                                                        if (hasChange && !mem.isEmpty() && !"{}".equals(mem)) {
                                                            memoryService.updateMemory(sessionId, mem)
                                                                    .doOnError(e -> System.err.println("❌ 记忆落库失败: " + e.getMessage()))
                                                                    .subscribe();
                                                        }

                                                        // 冲突审计日志（⚠️ 生产环境请改用 logging，避免 System.out 泄露敏感信息到 stdout）
                                                        if (conflicts.isArray() && conflicts.size() > 0) {
                                                            System.out.println("⚠️ 记忆冲突已消解: " + conflicts);
                                                        }

                                                        // 情景记忆：非空才写
                                                        if (episodic != null && !episodic.trim().isEmpty()) {
                                                            memoryService.saveEpisodicMemory(sessionId, episodic)
                                                                    .doOnError(e -> System.err.println("❌ 情景记忆落库失败: " + e.getMessage()))
                                                                    .subscribe();
                                                        }
                                                    } catch (Exception e) {
                                                        System.err.println("解析记忆响应失败: " + e.getMessage());
                                                    }
                                                });
                                    } else {
                                        monitorService.logAsync(traceId, sessionId, userQuery, "AGENT", cost, tokens.get(), "error", "Agent failed");
                                    }
                                });
                    });
                }))
                .doOnError(err -> {
                    System.err.println("❌ 核心链路异常: " + err.getMessage());
                    err.printStackTrace();
                });
    }

    private ServerSentEvent<String> createSse(String event, String data) {
        return ServerSentEvent.<String>builder().event(event).data(data).build();
    }
}