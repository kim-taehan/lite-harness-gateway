package ai.litellm.backend.domain

import com.fasterxml.jackson.databind.JsonNode
import jakarta.persistence.Column
import jakarta.persistence.Entity
import jakarta.persistence.Id
import jakarta.persistence.Table
import org.hibernate.annotations.JdbcTypeCode
import org.hibernate.type.SqlTypes
import java.time.Instant
import java.util.UUID

@Entity
@Table(name = "LiteLLM_DeletedVerificationToken")
class DeletedTokenEntity {
    @Id
    var id: String = UUID.randomUUID().toString()

    var token: String = ""
    var keyName: String? = null
    var keyAlias: String? = null
    var softBudgetCooldown: Boolean = false
    var spend: Double = 0.0
    var totalSpend: Double = 0.0
    var expires: Instant? = null

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Column(columnDefinition = "text[]")
    var models: List<String>? = null

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(columnDefinition = "jsonb")
    var aliases: JsonNode? = null

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(columnDefinition = "jsonb")
    var config: JsonNode? = null

    var userId: String? = null
    var teamId: String? = null
    var agentId: String? = null
    var projectId: String? = null

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(columnDefinition = "jsonb")
    var permissions: JsonNode? = null

    var maxParallelRequests: Int? = null

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(columnDefinition = "jsonb")
    var metadata: JsonNode? = null

    var blocked: Boolean? = null
    var tpmLimit: Long? = null
    var rpmLimit: Long? = null
    var tpdLimit: Long? = null
    var maxBudget: Double? = null
    var budgetDuration: String? = null
    var budgetResetAt: Instant? = null

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Column(columnDefinition = "text[]")
    var allowedCacheControls: List<String>? = null

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Column(columnDefinition = "text[]")
    var allowedRoutes: List<String>? = null

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Column(columnDefinition = "text[]")
    var policies: List<String>? = null

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Column(columnDefinition = "text[]")
    var accessGroupIds: List<String>? = null

    var keyType: String? = null

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(columnDefinition = "jsonb")
    var modelSpend: JsonNode? = null

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(columnDefinition = "jsonb")
    var modelMaxBudget: JsonNode? = null

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(columnDefinition = "jsonb")
    var budgetFallbacks: JsonNode? = null

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(columnDefinition = "jsonb")
    var routerSettings: JsonNode? = null

    var budgetId: String? = null
    var organizationId: String? = null
    var objectPermissionId: String? = null
    var createdAt: Instant? = null
    var createdBy: String? = null
    var updatedAt: Instant? = null
    var updatedBy: String? = null

    var rotationCount: Int? = null
    var autoRotate: Boolean? = null
    var rotationInterval: String? = null
    var lastRotationAt: Instant? = null
    var keyRotationAt: Instant? = null
    var lastActive: Instant? = null
    var settingsUpdatedAt: Instant? = null

    var deletedAt: Instant? = null
    var deletedBy: String? = null
    var deletedByApiKey: String? = null
    var litellmChangedBy: String? = null
}
