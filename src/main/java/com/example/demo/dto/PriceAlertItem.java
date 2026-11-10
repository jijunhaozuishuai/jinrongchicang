package com.example.demo.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record PriceAlertItem(
        Long id,
        String symbol,
        @JsonProperty("stock_name") String stockName,
        @JsonProperty("condition_type") String conditionType,
        Double threshold
) {}