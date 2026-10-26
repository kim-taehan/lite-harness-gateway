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
@Table(name = "LiteLLM_UserTable")
class UserEntity {
    @Id
    var userId: String = ""

    var userAlias: String? = null
    var teamId: String? = null
    var ssoUserId: String? = null
    var organizationId: String? = null
    var password: String? = null

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Column(name = "teams", columnDefinition = "text[]")
    var teams: List<String> = emptyList()

    var userRole: String? = null
    var maxBudget: Double? = null

    var spend: Double = 0.0

    var userEmail: String? = null

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Column(name = "models", columnDefinition = "text[]")
    var models: List<String>? = null

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "metadata", columnDefinition = "jsonb")
    var metadata: JsonNode = JsonNodeFactory.instance.objectNode()

    var maxParallelRequests: Int? = null
    var tpmLimit: Long? = null
    var rpmLimit: Long? = null
    var budgetDuration: String? = null
    var budgetResetAt: Instant? = null

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Column(name = "allowed_cache_controls", columnDefinition = "text[]")
    var allowedCacheControls: List<String> = emptyList()

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "model_spend", columnDefinition = "jsonb")
    var modelSpend: JsonNode = JsonNodeFactory.instance.objectNode()

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "model_max_budget", columnDefinition = "jsonb")
    var modelMaxBudget: JsonNode = JsonNodeFactory.instance.objectNode()

    var createdAt: Instant? = null
    var updatedAt: Instant? = null
    var objectPermissionId: String? = null

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Column(name = "policies", columnDefinition = "text[]")
    var policies: List<String> = emptyList()

    var passwordResetRequired: Boolean? = null
    var lastBreachCheckAt: Instant? = null
}
