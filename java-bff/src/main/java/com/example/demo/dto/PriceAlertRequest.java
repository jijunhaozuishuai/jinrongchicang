package com.example.demo.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

public record PriceAlertRequest(
        @NotBlank String userId,
        @NotBlank String symbol,
        String stockName,
        @NotBlank String conditionType,   // ABOVE / BELOW
        @NotNull Double threshold
) {}