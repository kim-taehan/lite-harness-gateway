package ai.litellm.backend.persistence

import ai.litellm.backend.domain.BudgetEntity
import ai.litellm.backend.domain.ProxyModelEntity
import ai.litellm.backend.domain.TeamEntity
import ai.litellm.backend.domain.UserEntity
import ai.litellm.backend.domain.VerificationTokenEntity
import ai.litellm.backend.repository.BudgetRepository
import ai.litellm.backend.repository.ProxyModelRepository
import ai.litellm.backend.repository.SpendLogRepository
import ai.litellm.backend.repository.TeamRepository
import ai.litellm.backend.repository.UserRepository
import ai.litellm.backend.repository.VerificationTokenRepository
import com.fasterxml.jackson.databind.node.JsonNodeFactory
import org.junit.jupiter.api.Test
import org.springframework.beans.factory.annotation.Autowired
import org.springframework.boot.test.context.SpringBootTest
import org.springframework.transaction.annotation.Transactional
import java.util.UUID
import kotlin.test.assertEquals
import kotlin.test.assertTrue

@SpringBootTest
class DataLayerRoundTripTest {
    @Autowired
    lateinit var keys: VerificationTokenRepository

    @Autowired
    lateinit var users: UserRepository

    @Autowired
    lateinit var teams: TeamRepository

    @Autowired
    lateinit var models: ProxyModelRepository

    @Autowired
    lateinit var budgets: BudgetRepository

    @Autowired
    lateinit var spendLogs: SpendLogRepository

    @Test
    @Transactional
    fun `verification token roundtrips jsonb and array columns`() {
        val token = "a".repeat(64)
        val meta = JsonNodeFactory.instance.objectNode().put("owner", "test")
        val entity = VerificationTokenEntity().apply {
            this.token = token
            userId = "roundtrip-user"
            aliases = JsonNodeFactory.instance.objectNode().put("gpt-4", "gpt-4o")
            metadata = meta
            modelSpend = JsonNodeFactory.instance.objectNode().put("gpt-4", 0.1)
            models = listOf("gpt-4", "gpt-4o")
            allowedRoutes = listOf("/chat/completions")
            maxBudget = 12.5
            rpmLimit = 42
        }
        keys.saveAndFlush(entity)

        val read = keys.findByToken(token).orElseThrow { AssertionError("inserted token not found") }
        assertEquals("roundtrip-user", read.userId)
        assertEquals(12.5, read.maxBudget)
        assertEquals(42L, read.rpmLimit)
        assertEquals("gpt-4o", read.aliases.get("gpt-4").asText())
        assertEquals(listOf("gpt-4", "gpt-4o"), read.models)
        assertEquals(listOf("/chat/completions"), read.allowedRoutes)
        assertEquals("test", read.metadata.get("owner").asText())
        assertEquals(0.1, read.modelSpend.get("gpt-4").asDouble())
    }

    @Test
    @Transactional
    fun `user roundtrips array and jsonb columns`() {
        val userId = UUID.randomUUID().toString()
        val entity = UserEntity().apply {
            this.userId = userId
            userRole = "internal_user"
            teams = listOf("team-1", "team-2")
            models = listOf("all-proxy-models")
            metadata = JsonNodeFactory.instance.objectNode().put("team", "core")
            spend = 1.25
        }
        users.saveAndFlush(entity)

        val read = users.findByUserId(userId).orElseThrow { AssertionError("inserted user not found") }
        assertEquals(listOf("team-1", "team-2"), read.teams)
        assertEquals(listOf("all-proxy-models"), read.models)
        assertEquals("core", read.metadata.get("team").asText())
        assertEquals(1.25, read.spend)
    }

    @Test
    @Transactional
    fun `team roundtrips members with roles`() {
        val teamId = UUID.randomUUID().toString()
        val members = JsonNodeFactory.instance.arrayNode()
            .add(JsonNodeFactory.instance.objectNode().put("role", "admin").put("user_id", "admin-1"))
        val entity = TeamEntity().apply {
            this.teamId = teamId
            teamAlias = "roundtrip team"
            membersWithRoles = members
            models = listOf("m1", "m2")
            maxBudget = 100.0
        }
        teams.saveAndFlush(entity)

        val read = teams.findByTeamId(teamId).orElseThrow { AssertionError("inserted team not found") }
        assertEquals(listOf("m1", "m2"), read.models)
        assertEquals(100.0, read.maxBudget)
        assertEquals("admin", read.membersWithRoles.get(0).get("role").asText())
        assertEquals("admin-1", read.membersWithRoles.get(0).get("user_id").asText())
    }

    @Test
    @Transactional
    fun `proxy model roundtrips params`() {
        val modelName = "kotlin-roundtrip-${UUID.randomUUID()}"
        val modelId = UUID.randomUUID().toString()
        val entity = ProxyModelEntity().apply {
            this.modelId = modelId
            this.modelName = modelName
            litellmParams = JsonNodeFactory.instance.objectNode()
                .put("model", "openai/$modelName").put("api_base", "http://localhost:9999")
            modelInfo = JsonNodeFactory.instance.objectNode()
                .put("id", modelId).put("db_model", true).put("direct_access", true)
            createdBy = "roundtrip"
            updatedBy = "roundtrip"
        }
        models.saveAndFlush(entity)

        val read = models.findByModelName(modelName).orElseThrow { AssertionError("inserted model not found") }
        assertEquals("openai/$modelName", read.litellmParams.get("model").asText())
        assertEquals(true, read.modelInfo!!.get("db_model").asBoolean())
    }

    @Test
    @Transactional
    fun `budget roundtrips`() {
        val budgetId = "budget-roundtrip-${UUID.randomUUID()}"
        val entity = BudgetEntity().apply {
            this.budgetId = budgetId
            maxBudget = 50.0
            budgetDuration = "30d"
            allowedModels = listOf("m1")
            createdBy = "roundtrip"
            updatedBy = "roundtrip"
        }
        budgets.saveAndFlush(entity)

        val read = budgets.findByBudgetId(budgetId).orElseThrow { AssertionError("inserted budget not found") }
        assertEquals(50.0, read.maxBudget)
        assertEquals("30d", read.budgetDuration)
        assertEquals(listOf("m1"), read.allowedModels)
    }

    @Test
    fun `spend aggregate is non-negative`() {
        assertTrue(spendLogs.sumSpend() >= 0.0)
    }
}
