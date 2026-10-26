package ai.litellm.backend.config

import com.zaxxer.hikari.HikariDataSource
import org.springframework.context.annotation.Bean
import org.springframework.context.annotation.Configuration
import org.springframework.context.annotation.Primary
import java.net.URI

@Configuration
class DataSourceConfig(private val properties: BackendProperties) {
    @Bean
    @Primary
    fun litellmDataSource(): HikariDataSource {
        val (url, username, password) = resolveConnection()
        val dataSource = HikariDataSource()
        dataSource.jdbcUrl = url
        if (!username.isNullOrBlank()) dataSource.username = username
        if (password != null && password.isNotBlank()) dataSource.password = password
        dataSource.isAutoCommit = true
        dataSource.maximumPoolSize = 10
        dataSource.minimumIdle = 2
        dataSource.idleTimeout = 30_000
        dataSource.maxLifetime = 900_000
        dataSource.connectionTimeout = 5_000
        return dataSource
    }

    private fun resolveConnection(): Triple<String, String?, String?> {
        val raw = properties.databaseUrl.trim()
        return when {
            raw.isBlank() -> Triple(defaultJdbcUrl(), "litellm", "litellm")
            raw.startsWith("jdbc:") -> Triple(raw, env("POSTGRES_USER"), env("POSTGRES_PASSWORD"))
            raw.startsWith("postgresql://") || raw.startsWith("postgres://") -> {
                val uri = URI.create(raw)
                val port = if (uri.port == -1) 5432 else uri.port
                val path = if (uri.path.isNullOrBlank()) "/litellm" else uri.path
                val jdbc = "jdbc:postgresql://${uri.host}:$port$path"
                val info = uri.userInfo?.split(":", limit = 2)
                Triple(jdbc, info?.getOrNull(0), info?.getOrNull(1))
            }
            else -> Triple(raw, env("POSTGRES_USER"), env("POSTGRES_PASSWORD"))
        }
    }

    private fun env(name: String): String? = System.getenv(name)?.takeIf { it.isNotBlank() }

    private fun defaultJdbcUrl(): String = "jdbc:postgresql://localhost:5435/litellm"
}
