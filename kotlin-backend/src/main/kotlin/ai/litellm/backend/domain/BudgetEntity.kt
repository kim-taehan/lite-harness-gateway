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
@Table(name = "LiteLLM_BudgetTable")
class BudgetEntity {
    @Id
    var budgetId: String = ""

    var maxBudget: Double? = null
    var softBudget: Double? = null
    var maxParallelRequests: Int? = null
    var tpmLimit: Long? = null
    var rpmLimit: Long? = null
    var tpdLimit: Long? = null

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "model_max_budget", columnDefinition = "jsonb")
    var modelMaxBudget: JsonNode? = null

    var budgetDuration: String? = null
    var budgetResetAt: Instant? = null

    var createdAt: Instant = Instant.now()
    var createdBy: String = ""
    var updatedAt: Instant = Instant.now()
    var updatedBy: String = ""

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Column(name = "allowed_models", columnDefinition = "text[]")
    var allowedModels: List<String>? = null

    var tempBudgetIncrease: Double? = null
    var tempBudgetExpiry: Instant? = null
}
