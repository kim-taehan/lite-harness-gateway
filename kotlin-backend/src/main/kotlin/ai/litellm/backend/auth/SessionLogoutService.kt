package ai.litellm.backend.auth

import ai.litellm.backend.repository.DeletedTokenRepository
import ai.litellm.backend.repository.VerificationTokenRepository
import org.springframework.stereotype.Service

sealed interface LogoutOutcome {
    data class Revoked(val wasActive: Boolean) : LogoutOutcome
    data class Forbidden(val message: String) : LogoutOutcome
}

@Service
class SessionLogoutService(
    private val tokens: VerificationTokenRepository,
    private val deletedTokens: DeletedTokenRepository,
) {
    fun revoke(principal: Principal): LogoutOutcome {
        if (principal.teamId != UI_DESIGN_TEAM_ID) {
            return LogoutOutcome.Forbidden(NON_SESSION_TOKEN_MESSAGE)
        }
        val hash = principal.tokenHash
        if (hash == null) return LogoutOutcome.Revoked(false)
        val row = tokens.findByToken(hash).orElse(null)
        if (row != null) {
            deletedTokens.save(deletedRecordOf(row, principal))
            tokens.delete(row)
            return LogoutOutcome.Revoked(true)
        }
        return LogoutOutcome.Revoked(false)
    }

    companion object {
        const val NON_SESSION_TOKEN_MESSAGE = "Only UI session tokens can be revoked through this endpoint."
    }
}
