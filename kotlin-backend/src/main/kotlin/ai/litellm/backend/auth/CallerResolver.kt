package ai.litellm.backend.auth

import ai.litellm.backend.config.BackendProperties
import ai.litellm.backend.repository.UserRepository
import ai.litellm.backend.repository.VerificationTokenRepository
import ai.litellm.backend.web.ProxyError
import org.springframework.stereotype.Service
import java.time.Instant

@Service
class CallerResolver(
    private val tokens: VerificationTokenRepository,
    private val users: UserRepository,
    properties: BackendProperties,
) {
    private val masterKeyHash: String? =
        properties.masterKey.takeIf { it.isNotBlank() }?.let { Hashing.sha256Hex(it) }

    fun resolve(headerKey: String?): Principal {
        val candidate = headerKey?.takeIf { it.isNotBlank() }
            ?: throw ProxyError.noApiKeyPassed()
        if (masterKeyHash != null && constantTimeEquals(Hashing.sha256Hex(candidate), masterKeyHash!!)) {
            return Principal(
                source = AuthSource.MASTER_KEY,
                tokenHash = Hashing.sha256Hex(candidate),
                userId = "default_user_id",
                userRole = "proxy_admin",
                userEmail = null,
                teamId = null,
                organizationId = null,
                rawKey = candidate,
            )
        }
        if (!candidate.startsWith("sk-")) {
            throw ProxyError.virtualKeyExpected(candidate)
        }
        return lookupToken(candidate)
    }

    private fun lookupToken(rawKey: String): Principal {
        val hash = Hashing.sha256Hex(rawKey)
        val token = tokens.findByToken(hash)
            .orElseThrow { ProxyError.tokenNotFound(rawKey, hash) }
        val now = Instant.now()
        val expires = token.expires
        if (expires != null && expires.isBefore(now)) {
            throw ProxyError(
                "Authentication Error, expired key passed. Please regenerate a valid key via `/key/generate`.",
                "auth_error",
                "key",
                401,
            )
        }
        if (token.blocked == true) {
            throw ProxyError.forbidden("Key is blocked")
        }
        val user = token.userId?.let { users.findByUserId(it).orElse(null) }
        val role = user?.userRole ?: token.teamId?.let { "team" }
        return Principal(
            source = AuthSource.API_KEY,
            tokenHash = hash,
            userId = token.userId,
            userRole = role,
            userEmail = user?.userEmail,
            teamId = token.teamId,
            organizationId = token.organizationId,
            rawKey = rawKey,
        )
    }

    private fun constantTimeEquals(a: String, b: String): Boolean {
        val ab = a.toByteArray()
        val bb = b.toByteArray()
        if (ab.size != bb.size) return false
        var result = 0
        for (i in ab.indices) result = result or (ab[i].toInt() xor bb[i].toInt())
        return result == 0
    }
}
