package com.example.demo.controller;

import com.example.demo.dto.ChatRequest;
import com.example.demo.dto.FeedbackRequest;
import com.example.demo.service.ChatService;
import com.example.demo.service.FeedbackService;
import jakarta.validation.Valid;
import org.springframework.http.MediaType;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import java.util.UUID;

@RestController
@CrossOrigin(origins = "*")
public class ChatController {
    private final ChatService chatService;
    private final FeedbackService feedbackService;

    public ChatController(ChatService chatService, FeedbackService feedbackService) {
        this.chatService = chatService; this.feedbackService = feedbackService;
    }

    @PostMapping(value = "/chat", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<ServerSentEvent<String>> chat(@Valid @RequestBody ChatRequest req) {
        return chatService.chat(req.sessionId(), req.message(), UUID.randomUUID().toString().substring(0, 8));
    }

    @PostMapping("/feedback")
    public Mono<Void> feedback(@Valid @RequestBody FeedbackRequest req) {
        return feedbackService.submit(req.traceId(), req.feedback());
    }
}
