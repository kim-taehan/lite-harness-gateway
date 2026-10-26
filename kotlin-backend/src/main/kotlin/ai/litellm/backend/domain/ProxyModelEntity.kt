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
@Table(name = "LiteLLM_ProxyModelTable")
class ProxyModelEntity {
    @Id
    var modelId: String = ""

    var modelName: String = ""

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "litellm_params", columnDefinition = "jsonb")
    var litellmParams: JsonNode = com.fasterxml.jackson.databind.node.JsonNodeFactory.instance.objectNode()

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "model_info", columnDefinition = "jsonb")
    var modelInfo: JsonNode? = null

    var createdAt: Instant = Instant.now()
    var createdBy: String = ""
    var updatedAt: Instant = Instant.now()
    var updatedBy: String = ""

    var blocked: Boolean = false
}
