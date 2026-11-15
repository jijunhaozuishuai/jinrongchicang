package com.example.demo.controller;

import com.example.demo.dto.PriceAlertItem;
import com.example.demo.dto.PriceAlertRequest;
import com.example.demo.service.PriceAlertService;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

@RestController
@RequestMapping("/alerts")
@CrossOrigin(origins = "*")
public class PriceAlertController {
    private final PriceAlertService svc;

    public PriceAlertController(PriceAlertService svc) {
        this.svc = svc;
    }

    @PostMapping
    public Mono<Long> create(@Valid @RequestBody PriceAlertRequest req) {
        return svc.create(req);
    }

    @GetMapping
    public Flux<PriceAlertItem> list(@RequestParam String userId) {
        return svc.listActive(userId).flatMapMany(Flux::fromIterable);
    }

    @DeleteMapping("/{id}")
    public Mono<Void> cancel(@RequestParam String userId, @PathVariable Long id) {
        return svc.cancel(userId, id);
    }
}