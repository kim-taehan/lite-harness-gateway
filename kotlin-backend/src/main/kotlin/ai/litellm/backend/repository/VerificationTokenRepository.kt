package ai.litellm.backend.repository

import ai.litellm.backend.domain.VerificationTokenEntity
import org.springframework.data.jpa.repository.JpaRepository
import org.springframework.data.jpa.repository.Query
import org.springframework.stereotype.Repository
import java.util.Optional

@Repository
interface VerificationTokenRepository : JpaRepository<VerificationTokenEntity, String> {
    fun findByToken(token: String): Optional<VerificationTokenEntity>

    fun findByUserId(userId: String): List<VerificationTokenEntity>

    fun findByTeamId(teamId: String): List<VerificationTokenEntity>

    fun findByOrganizationId(organizationId: String): List<VerificationTokenEntity>

    @Query("select coalesce(sum(t.spend), 0.0) from VerificationTokenEntity t")
    fun sumSpend(): Double

    @Query(
        "select t from VerificationTokenEntity t where t.teamId is null and t.userId is null and t.organizationId is null"
    )
    fun findOrphanKeys(): List<VerificationTokenEntity>
}
