package ai.litellm.backend.auth

import ai.litellm.backend.config.BackendProperties
import ai.litellm.backend.config.YamlConfigProvider
import ai.litellm.backend.domain.UserEntity
import ai.litellm.backend.domain.VerificationTokenEntity
import ai.litellm.backend.repository.UserRepository
import ai.litellm.backend.repository.VerificationTokenRepository
import ai.litellm.backend.web.ProxyError
import com.fasterxml.jackson.databind.node.JsonNodeFactory
import org.springframework.stereotype.Service
import java.time.Instant

data class LoginOutcome(
    val claims: UiSessionClaims,
    val jwt: String,
)

const val PROXY_ADMIN_USER_ID = "default_user_id"
const val UI_DESIGN_TEAM_ID = "litellm-dashboard"
const val INVALID_UI_CREDENTIALS_MESSAGE =
    "Invalid credentials used to access UI. Check 'UI_USERNAME' and 'UI_PASSWORD', or the password set for your user"
const val INVALID_USER_PASSWORD_MESSAGE =
    "Invalid credentials used to access UI. Check the password set for your user"

@Service
class LoginService(
    private val properties: BackendProperties,
    private val yaml: YamlConfigProvider,
    private val keys: VerificationTokenRepository,
    private val users: UserRepository,
    private val uiSessionJwt: UiSessionJwt,
) {
    fun login(username: String, password: String): LoginOutcome {
        val ttlSeconds = DurationParser.durationInSeconds(properties.uiSessionDuration)

        if (envCredsMatch(username, password)) {
            val key = issueSessionKey(PROXY_ADMIN_USER_ID, "proxy_admin", ttlSeconds)
            ensureAdminUserRow()
            return buildOutcome(PROXY_ADMIN_USER_ID, key, null, "proxy_admin", false, ttlSeconds)
        }

        val user = users.findByUserEmail(username).firstOrNull()
        if (user != null) {
            val stored = user.password
            if (stored == null) {
                throw ProxyError(
                    "User has no password set. Please set a password for the user via `/user/update`.",
                    "auth_error",
                    "password",
                    401,
                )
            }
            if (Hashing.verifyPassword(password, stored)) {
                val role = user.userRole ?: "internal_user_viewer"
                val key = issueSessionKey(user.userId, role, ttlSeconds)
                return buildOutcome(
                    user.userId,
                    key,
                    user.userEmail,
                    role,
                    user.passwordResetRequired == true,
                    ttlSeconds,
                )
            }
        }

        val message =
            if (yaml.yamlConfig.generalSettings["disable_env_credential_login"] == true) {
                INVALID_USER_PASSWORD_MESSAGE
            } else {
                INVALID_UI_CREDENTIALS_MESSAGE
            }
        throw ProxyError.invalidCredentials(message)
    }

    private fun envCredsMatch(username: String, password: String): Boolean {
        if (properties.masterKey.isNotBlank() && username == properties.masterKey) return true
        val envUser = properties.uiUsername
        val envPass = properties.uiPassword
        return envUser.isNotBlank() && username == envUser && password == envPass
    }

    private fun ensureAdminUserRow() {
        val existing = users.findByUserId(PROXY_ADMIN_USER_ID).orElse(null)
        if (existing == null) {
            users.saveAndFlush(
                UserEntity().apply {
                    userId = PROXY_ADMIN_USER_ID
                    userRole = "proxy_admin"
                }
            )
        } else if (existing.userRole != "proxy_admin") {
            existing.userRole = "proxy_admin"
            users.save(existing)
        }
    }

    private fun issueSessionKey(userId: String, role: String, ttlSeconds: Long): String {
        val raw = "sk-" + Hashing.randomUrlSafeToken(properties.keyLength)
        val now = Instant.now()
        val empty = JsonNodeFactory.instance.objectNode()
        val token = VerificationTokenEntity().apply {
            this.token = Hashing.sha256Hex(raw)
            this.userId = userId
            teamId = UI_DESIGN_TEAM_ID
            maxBudget = 1.0
            expires = now.plusSeconds(ttlSeconds)
            createdAt = now
            updatedAt = now
            createdBy = userId
            updatedBy = userId
            aliases = empty
            config = empty
            metadata = empty
            permissions = empty
            modelSpend = empty
            modelMaxBudget = empty
            budgetFallbacks = empty
        }
        keys.saveAndFlush(token)
        return raw
    }

    private fun buildOutcome(
        userId: String,
        key: String,
        email: String?,
        role: String,
        passwordResetRequired: Boolean,
        ttlSeconds: Long,
    ): LoginOutcome {
        val claims = UiSessionClaims(
            userId = userId,
            key = key,
            userEmail = email,
            userRole = role,
            loginMethod = "username_password",
            premiumUser = false,
            authHeaderName = yaml.yamlConfig.config.keyHeaderName(),
            disabledNonAdminPersonalKeyCreation = false,
            serverRootPath = "",
            passwordResetRequired = passwordResetRequired,
        )
        return LoginOutcome(claims, uiSessionJwt.encode(claims, ttlSeconds))
    }
}
