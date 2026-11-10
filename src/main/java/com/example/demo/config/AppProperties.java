package com.example.demo.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;

@Data
@ConfigurationProperties(prefix = "app")
public class AppProperties {
    private Agent agent = new Agent();
    private Cache cache = new Cache();
    private Chat chat = new Chat();

    @Data
    public static class Agent {
        private String baseUrl; private String streamPath; private String memoryPath; private String internalToken;
    }
    @Data
    public static class Cache { private long ttlSeconds = 300; }
    @Data
    public static class Chat { private int maxConcurrent = 20; private int historyLimit = 10; }
}
