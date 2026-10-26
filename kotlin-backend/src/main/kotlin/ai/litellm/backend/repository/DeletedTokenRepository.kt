package ai.litellm.backend.repository

import ai.litellm.backend.domain.DeletedTokenEntity
import org.springframework.data.jpa.repository.JpaRepository
import org.springframework.stereotype.Repository
import java.util.Optional

@Repository
interface DeletedTokenRepository : JpaRepository<DeletedTokenEntity, String> {
    fun findByToken(token: String): Optional<DeletedTokenEntity>
}
