package ai.litellm.backend.auth

import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec
import java.nio.charset.StandardCharsets
import java.util.Base64

data class UiSessionClaims(
    val userId: String,
    val key: String,
    val userEmail: String?,
    val userRole: String,
    val loginMethod: String,
    val premiumUser: Boolean,
    val authHeaderName: String,
    val disabledNonAdminPersonalKeyCreation: Boolean,
    val serverRootPath: String,
    val passwordResetRequired: Boolean,
)

class UiSessionJwt(private val masterKey: String) {
    private val urlEncoder = Base64.getUrlEncoder().withoutPadding()

    fun encode(claims: UiSessionClaims, ttlSeconds: Long): String {
        val header = urlEncoder.encodeToString(
            """{"alg":"HS256","typ":"JWT"}""".toByteArray(StandardCharsets.UTF_8)
        )
        val payloadJson = buildString {
            append("{\"user_id\":").append(jsonString(claims.userId))
            append(",\"key\":").append(jsonString(claims.key))
            append(",\"user_email\":").append(claims.userEmail?.let { jsonString(it) } ?: "null")
            append(",\"user_role\":").append(jsonString(claims.userRole))
            append(",\"login_method\":").append(jsonString(claims.loginMethod))
            append(",\"premium_user\":").append(if (claims.premiumUser) "true" else "false")
            append(",\"auth_header_name\":").append(jsonString(claims.authHeaderName))
            append(",\"disabled_non_admin_personal_key_creation\":")
            .append(if (claims.disabledNonAdminPersonalKeyCreation) "true" else "false")
            append(",\"server_root_path\":").append(jsonString(claims.serverRootPath))
            append(",\"password_reset_required\":").append(if (claims.passwordResetRequired) "true" else "false")
            append(",\"exp\":").append(System.currentTimeMillis() / 1000 + ttlSeconds)
            append('}')
        }
        val payload = urlEncoder.encodeToString(payloadJson.toByteArray(StandardCharsets.UTF_8))
        val signature = sign("$header.$payload")
        return "$header.$payload.$signature"
    }

    fun decode(token: String): UiSessionClaims? {
        val parts = token.split(".")
        if (parts.size != 3) return null
        if (sign("${parts[0]}.${parts[1]}") != parts[2]) return null
        return try {
            val payload = String(Base64.getUrlDecoder().decode(parts[1]), StandardCharsets.UTF_8)
            parseClaims(payload)
        } catch (e: Exception) {
            null
        }
    }

    private fun parseClaims(payload: String): UiSessionClaims? {
        val exp = extractNumber(payload, "exp") ?: return null
        if (exp <= System.currentTimeMillis() / 1000) return null
        return UiSessionClaims(
            userId = extractString(payload, "user_id") ?: return null,
            key = extractString(payload, "key") ?: "",
            userEmail = extractString(payload, "user_email"),
            userRole = extractString(payload, "user_role") ?: "internal_user",
            loginMethod = extractString(payload, "login_method") ?: "username_password",
            premiumUser = payload.contains("\"premium_user\":true"),
            authHeaderName = extractString(payload, "auth_header_name") ?: "Authorization",
            disabledNonAdminPersonalKeyCreation =
                payload.contains("\"disabled_non_admin_personal_key_creation\":true"),
            serverRootPath = extractString(payload, "server_root_path") ?: "",
            passwordResetRequired = payload.contains("\"password_reset_required\":true"),
        )
    }

    private fun extractString(payload: String, field: String): String? {
        val marker = "\"$field\":"
        val idx = payload.indexOf(marker)
        if (idx < 0) return null
        val start = idx + marker.length
        if (payload[start] != '"') {
            val rest = payload.substring(start)
            val end = minOfIndex(rest.indexOf(','), rest.indexOf('}'), rest.length)
            return rest.substring(0, end).trim().takeIf { it != "null" && it.isNotEmpty() }
        }
        val end = payload.indexOf('"', start + 1)
        if (end < 0) return null
        return payload.substring(start + 1, end)
            .replace("\\\\", "\\")
            .replace("\\\"", "\"")
    }

    private fun extractNumber(payload: String, field: String): Long? {
        val marker = "\"$field\":"
        val idx = payload.indexOf(marker)
        if (idx < 0) return null
        val rest = payload.substring(idx + marker.length)
        val end = rest.indexOfFirst { !it.isDigit() }.let { if (it < 0) rest.length else it }
        return rest.substring(0, end).toLongOrNull()
    }

    private fun minOfIndex(vararg candidates: Int): Int =
        candidates.filter { it >= 0 }.minOrNull() ?: candidates.max()

    private fun jsonString(value: String): String =
        "\"${value.replace("\\", "\\\\").replace("\"", "\\\"")}\""

    private fun coalesce(value: Int, fallback: Int): Int = if (value < 0) fallback else value

    private fun sign(signingInput: String): String {
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(masterKey.toByteArray(StandardCharsets.UTF_8), "HmacSHA256"))
        return urlEncoder.encodeToString(mac.doFinal(signingInput.toByteArray(StandardCharsets.UTF_8)))
    }
}
