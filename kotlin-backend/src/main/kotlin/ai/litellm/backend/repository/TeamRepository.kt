package ai.litellm.backend.repository

import ai.litellm.backend.domain.TeamEntity
import org.springframework.data.jpa.repository.JpaRepository
import org.springframework.data.jpa.repository.Query
import org.springframework.stereotype.Repository
import java.util.Optional

@Repository
interface TeamRepository : JpaRepository<TeamEntity, String> {
    fun findByTeamId(teamId: String): Optional<TeamEntity>

    fun findByTeamAlias(teamAlias: String): Optional<TeamEntity>

    @Query("select coalesce(sum(t.spend), 0.0) from TeamEntity t")
    fun sumSpend(): Double
}
