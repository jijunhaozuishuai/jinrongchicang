package com.example.demo.client;

import com.example.demo.config.AppProperties;
import com.example.demo.dto.AgentStreamRequest;
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

import java.util.Map;

@Component
public class AgentClient {
    private final WebClient webClient;
    private final AppProperties props;

    public AgentClient(WebClient agentWebClient, AppProperties props) {
        this.webClient = agentWebClient;
        this.props = props;
    }

    public Flux<ServerSentEvent<String>> streamChat(AgentStreamRequest req) {
        return webClient.post().uri(props.getAgent().getStreamPath())
                .header("X-Internal-Token", props.getAgent().getInternalToken())
                .bodyValue(req).retrieve()
                .bodyToFlux(new ParameterizedTypeReference<ServerSentEvent<String>>() {});
    }

    public Mono<String> extractMemory(Map<String, String> payload) {
        return webClient.post().uri(props.getAgent().getMemoryPath())
                .header("X-Internal-Token", props.getAgent().getInternalToken())
                .bodyValue(payload).retrieve().bodyToMono(String.class);
    }

    /** 新增：价格预警检查 */
    public Mono<JsonNode> priceCheck(Map<String, Object> payload) {
        return webClient.post().uri("/internal/agent/proactive/price_check")
                .header("X-Internal-Token", props.getAgent().getInternalToken())
                .bodyValue(payload).retrieve()
                .bodyToMono(JsonNode.class);
    }
}