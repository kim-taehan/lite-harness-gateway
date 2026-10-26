package ai.litellm.backend.repository

import ai.litellm.backend.domain.BudgetEntity
import org.springframework.data.jpa.repository.JpaRepository
import org.springframework.stereotype.Repository
import java.util.Optional

@Repository
interface BudgetRepository : JpaRepository<BudgetEntity, String> {
    fun findByBudgetId(budgetId: String): Optional<BudgetEntity>
}
