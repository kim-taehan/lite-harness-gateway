package ai.litellm.backend.auth

enum class AuthSource {
    API_KEY,
    MASTER_KEY,
}

data class Principal(
    val source: AuthSource,
    val tokenHash: String?,
    val userId: String?,
    val userRole: String?,
    val userEmail: String?,
    val teamId: String?,
    val organizationId: String?,
    val rawKey: String? = null,
) {
    val isProxyAdmin: Boolean
        get() = source == AuthSource.MASTER_KEY || userRole == "proxy_admin"
}
