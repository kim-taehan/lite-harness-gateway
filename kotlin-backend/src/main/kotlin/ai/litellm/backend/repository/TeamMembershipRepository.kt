package ai.litellm.backend.repository

import ai.litellm.backend.domain.TeamMembershipEntity
import org.springframework.data.jpa.repository.JpaRepository
import org.springframework.stereotype.Repository

@Repository
interface TeamMembershipRepository : JpaRepository<TeamMembershipEntity, TeamMembershipEntity.Key> {
    fun findByUserId(userId: String): List<TeamMembershipEntity>

    fun findByTeamId(teamId: String): List<TeamMembershipEntity>

    fun existsByUserIdAndTeamId(userId: String, teamId: String): Boolean

    fun deleteByUserIdAndTeamId(userId: String, teamId: String)
}
