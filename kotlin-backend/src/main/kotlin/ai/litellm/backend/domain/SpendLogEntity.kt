package ai.litellm.backend.domain

import com.fasterxml.jackson.databind.JsonNode
import com.fasterxml.jackson.databind.node.JsonNodeFactory
import org.hibernate.annotations.JdbcTypeCode
import jakarta.persistence.Column
import jakarta.persistence.Entity
import jakarta.persistence.Id
import jakarta.persistence.Table
import org.hibernate.type.SqlTypes
import java.time.Instant

@Entity
@Table(name = "LiteLLM_SpendLogs")
class SpendLogEntity {
    @Id
    var requestId: String = ""

    var callType: String = ""

    var apiKey: String = ""

    var spend: Double = 0.0

    var totalTokens: Long = 0
    var promptTokens: Long = 0
    var completionTokens: Long = 0

    var startTime: Instant = Instant.now()
    var endTime: Instant = Instant.now()
    var completionStartTime: Instant? = null

    var model: String = ""
    var modelId: String = ""
    var modelGroup: String = ""
    var customLlmProvider: String = ""
    var apiBase: String = ""
    var user: String = ""

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "metadata", columnDefinition = "jsonb")
    var metadata: JsonNode? = null

    var cacheHit: String = ""
    var cacheKey: String = ""

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "request_tags", columnDefinition = "jsonb")
    var requestTags: JsonNode? = null

    var teamId: String? = null
    var endUser: String? = null
    var requesterIpAddress: String? = null

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "messages", columnDefinition = "jsonb")
    var messages: JsonNode? = null

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "response", columnDefinition = "jsonb")
    var response: JsonNode? = null

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "proxy_server_request", columnDefinition = "jsonb")
    var proxyServerRequest: JsonNode? = null

    var sessionId: String? = null
    var status: String? = null
    var mcpNamespacedToolName: String? = null
    var organizationId: String? = null
    var agentId: String? = null
    var requestDurationMs: Long? = null

    var createdAt: Instant = Instant.now()
    var updatedAt: Instant = Instant.now()

    var litellmCallId: String? = null
    var billingAgentId: String? = null
}
