package com.example.demo.dto;
import jakarta.validation.constraints.NotBlank;
public record FeedbackRequest(@NotBlank String traceId, @NotBlank String feedback) {}
