package com.example.demo.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;
import java.util.concurrent.Executor;

@Configuration
public class AsyncConfig {
    @Bean("monitorExecutor")
    public Executor monitorExecutor() {
        ThreadPoolTaskExecutor e = new ThreadPoolTaskExecutor();
        e.setCorePoolSize(2); e.setMaxPoolSize(8); e.setQueueCapacity(500);
        e.setThreadNamePrefix("monitor-"); e.initialize(); return e;
    }
}
