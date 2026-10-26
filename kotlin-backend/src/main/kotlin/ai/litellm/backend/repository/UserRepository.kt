package ai.litellm.backend.repository

import ai.litellm.backend.domain.UserEntity
import org.springframework.data.jpa.repository.JpaRepository
import org.springframework.data.jpa.repository.Query
import org.springframework.stereotype.Repository
import java.util.Optional

@Repository
interface UserRepository : JpaRepository<UserEntity, String> {
    fun findByUserId(userId: String): Optional<UserEntity>

    fun findByUserEmail(userEmail: String): List<UserEntity>

    fun existsByUserId(userId: String): Boolean

    @Query("select coalesce(sum(u.spend), 0.0) from UserEntity u")
    fun sumSpend(): Double
}
