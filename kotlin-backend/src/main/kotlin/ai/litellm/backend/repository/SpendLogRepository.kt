package ai.litellm.backend.repository

import ai.litellm.backend.domain.SpendLogEntity
import org.springframework.data.domain.Pageable
import org.springframework.data.jpa.repository.JpaRepository
import org.springframework.data.jpa.repository.Query
import org.springframework.data.repository.query.Param
import org.springframework.stereotype.Repository
import java.time.Instant

@Repository
interface SpendLogRepository : JpaRepository<SpendLogEntity, String> {
    @Query("select coalesce(sum(s.spend), 0.0) from SpendLogEntity s")
    fun sumSpend(): Double

    @Query(
        "select coalesce(sum(s.spend), 0.0) from SpendLogEntity s where s.user = :user"
    )
    fun sumSpendByUser(@Param("user") user: String): Double

    @Query(
        "select coalesce(sum(s.spend), 0.0) from SpendLogEntity s where s.teamId = :teamId"
    )
    fun sumSpendByTeam(@Param("teamId") teamId: String): Double

    @Query(
        "select s from SpendLogEntity s where s.startTime >= :since order by s.startTime desc"
    )
    fun findRecent(@Param("since") since: Instant, pageable: Pageable): List<SpendLogEntity>
}
