package ai.litellm.backend.repository

import ai.litellm.backend.domain.AuditLogEntity
import org.springframework.data.jpa.repository.JpaRepository
import org.springframework.data.jpa.repository.Query
import org.springframework.data.repository.query.Param
import org.springframework.stereotype.Repository
import java.time.Instant

@Repository
interface AuditLogRepository : JpaRepository<AuditLogEntity, String> {
    @Query(
        "select a from AuditLogEntity a where a.updatedAt >= :since order by a.updatedAt desc"
    )
    fun findRecent(@Param("since") since: Instant): List<AuditLogEntity>

    fun findByTableNameAndObjectId(tableName: String, objectId: String): List<AuditLogEntity>
}
