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
@Table(name = "LiteLLM_TeamTable")
class TeamEntity {
    @Id
    var teamId: String = ""

    var teamAlias: String? = null
    var organizationId: String? = null

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Column(name = "admins", columnDefinition = "text[]")
    var admins: List<String>? = null

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Column(name = "members", columnDefinition = "text[]")
    var members: List<String>? = null

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "members_with_roles", columnDefinition = "jsonb")
    var membersWithRoles: JsonNode = JsonNodeFactory.instance.objectNode()

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "metadata", columnDefinition = "jsonb")
    var metadata: JsonNode = JsonNodeFactory.instance.objectNode()

    var maxBudget: Double? = null

    var spend: Double = 0.0

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Column(name = "models", columnDefinition = "text[]")
    var models: List<String>? = null

    var maxParallelRequests: Int? = null
    var tpmLimit: Long? = null
    var rpmLimit: Long? = null
    var tpdLimit: Long? = null
    var softBudget: Double? = null
    var budgetDuration: String? = null
    var budgetResetAt: Instant? = null

    var blocked: Boolean = false

    var createdAt: Instant = Instant.now()
    var updatedAt: Instant = Instant.now()

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "model_spend", columnDefinition = "jsonb")
    var modelSpend: JsonNode = JsonNodeFactory.instance.objectNode()

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "model_max_budget", columnDefinition = "jsonb")
    var modelMaxBudget: JsonNode = JsonNodeFactory.instance.objectNode()

    var modelId: Int? = null

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Column(name = "team_member_permissions", columnDefinition = "text[]")
    var teamMemberPermissions: List<String> = emptyList()

    var objectPermissionId: String? = null

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "router_settings", columnDefinition = "jsonb")
    var routerSettings: JsonNode = JsonNodeFactory.instance.objectNode()

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Column(name = "policies", columnDefinition = "text[]")
    var policies: List<String> = emptyList()

    var allowTeamGuardrailConfig: Boolean = false

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Column(name = "access_group_ids", columnDefinition = "text[]")
    var accessGroupIds: List<String> = emptyList()

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "budget_limits", columnDefinition = "jsonb")
    var budgetLimits: JsonNode? = null

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Column(name = "default_team_member_models", columnDefinition = "text[]")
    var defaultTeamMemberModels: List<String> = emptyList()
}
