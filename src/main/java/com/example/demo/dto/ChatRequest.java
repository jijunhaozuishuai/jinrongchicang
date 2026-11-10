package com.example.demo.dto;
import jakarta.validation.constraints.NotBlank;
public record ChatRequest(@NotBlank String message, @NotBlank String sessionId) {}
