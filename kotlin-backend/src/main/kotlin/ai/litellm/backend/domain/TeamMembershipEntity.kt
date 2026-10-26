package ai.litellm.backend.domain

import jakarta.persistence.Entity
import jakarta.persistence.Id
import jakarta.persistence.IdClass
import jakarta.persistence.Table

@Entity
@Table(name = "LiteLLM_TeamMembership")
@IdClass(TeamMembershipEntity.Key::class)
class TeamMembershipEntity {
    @Id
    var userId: String = ""

    @Id
    var teamId: String = ""

    var spend: Double = 0.0

    var budgetId: String? = null

    var totalSpend: Double = 0.0

    data class Key(val userId: String = "", val teamId: String = "")
}
