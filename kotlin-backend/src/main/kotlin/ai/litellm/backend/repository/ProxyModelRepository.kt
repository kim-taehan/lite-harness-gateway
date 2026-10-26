package ai.litellm.backend.repository

import ai.litellm.backend.domain.ProxyModelEntity
import org.springframework.data.jpa.repository.JpaRepository
import org.springframework.stereotype.Repository
import java.util.Optional

@Repository
interface ProxyModelRepository : JpaRepository<ProxyModelEntity, String> {
    fun findByModelName(modelName: String): Optional<ProxyModelEntity>

    fun existsByModelName(modelName: String): Boolean
}
