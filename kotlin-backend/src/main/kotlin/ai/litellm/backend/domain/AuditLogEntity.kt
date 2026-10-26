package ai.litellm.backend.domain

import com.fasterxml.jackson.databind.JsonNode
import org.hibernate.annotations.JdbcTypeCode
import jakarta.persistence.Column
import jakarta.persistence.Entity
import jakarta.persistence.Id
import jakarta.persistence.Table
import org.hibernate.type.SqlTypes
import java.time.Instant

@Entity
@Table(name = "LiteLLM_AuditLog")
class AuditLogEntity {
    @Id
    var id: String = ""

    var updatedAt: Instant = Instant.now()
    var changedBy: String = ""
    var changedByApiKey: String = ""
    var action: String = ""
    var tableName: String = ""
    var objectId: String = ""

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "before_value", columnDefinition = "jsonb")
    var beforeValue: JsonNode? = null

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "updated_values", columnDefinition = "jsonb")
    var updatedValues: JsonNode? = null
}
