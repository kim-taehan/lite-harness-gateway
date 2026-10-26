package ai.litellm.backend.config

import org.springframework.boot.context.properties.ConfigurationProperties

@ConfigurationProperties(prefix = "litellm")
data class BackendProperties(
    val masterKey: String = "",
    val databaseUrl: String = "",
    val configYamlPath: String = "config.yaml",
    val uiUsername: String = "",
    val uiPassword: String = "",
    val uiSessionDuration: String = "24h",
    val keyLength: Int = 16,
)
