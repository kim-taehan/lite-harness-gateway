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
@Table(name = "LiteLLM_VerificationToken")
class VerificationTokenEntity {
    @Id
    var token: String = ""

    var keyName: String? = null
    var keyAlias: String? = null

    var softBudgetCooldown: Boolean = false

    var spend: Double = 0.0

    var expires: Instant? = null

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Column(name = "models", columnDefinition = "text[]")
    var models: List<String>? = null

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "aliases", columnDefinition = "jsonb")
    var aliases: JsonNode = JsonNodeFactory.instance.objectNode()

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "config", columnDefinition = "jsonb")
    var config: JsonNode = JsonNodeFactory.instance.objectNode()

    var userId: String? = null
    var teamId: String? = null

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "permissions", columnDefinition = "jsonb")
    var permissions: JsonNode = JsonNodeFactory.instance.objectNode()

    var maxParallelRequests: Int? = null

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "metadata", columnDefinition = "jsonb")
    var metadata: JsonNode = JsonNodeFactory.instance.objectNode()

    var blocked: Boolean? = null
    var tpmLimit: Long? = null
    var rpmLimit: Long? = null
    var tpdLimit: Long? = null
    var maxBudget: Double? = null
    var budgetDuration: String? = null
    var budgetResetAt: Instant? = null

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Column(name = "allowed_cache_controls", columnDefinition = "text[]")
    var allowedCacheControls: List<String>? = null

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "model_spend", columnDefinition = "jsonb")
    var modelSpend: JsonNode = JsonNodeFactory.instance.objectNode()

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "model_max_budget", columnDefinition = "jsonb")
    var modelMaxBudget: JsonNode = JsonNodeFactory.instance.objectNode()

    var budgetId: String? = null
    var organizationId: String? = null
    var createdAt: Instant? = null
    var createdBy: String? = null
    var updatedAt: Instant? = null
    var updatedBy: String? = null

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Column(name = "allowed_routes", columnDefinition = "text[]")
    var allowedRoutes: List<String>? = null

    var objectPermissionId: String? = null
    var autoRotate: Boolean? = null
    var keyRotationAt: Instant? = null
    var lastRotationAt: Instant? = null
    var rotationCount: Int? = null
    var rotationInterval: String? = null
    var projectId: String? = null

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "router_settings", columnDefinition = "jsonb")
    var routerSettings: JsonNode? = null

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Column(name = "policies", columnDefinition = "text[]")
    var policies: List<String>? = null

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Column(name = "access_group_ids", columnDefinition = "text[]")
    var accessGroupIds: List<String>? = null

    var lastActive: Instant? = null
    var agentId: String? = null

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "budget_limits", columnDefinition = "jsonb")
    var budgetLimits: JsonNode? = null

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "budget_fallbacks", columnDefinition = "jsonb")
    var budgetFallbacks: JsonNode = JsonNodeFactory.instance.objectNode()

    var keyType: String? = null
    var settingsUpdatedAt: Instant? = null

    var totalSpend: Double = 0.0
}
