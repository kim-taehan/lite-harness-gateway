package ai.litellm.backend.auth

import jakarta.servlet.http.HttpServletRequest
import ai.litellm.backend.web.ProxyError

const val PRINCIPAL_ATTR = "principal"

fun requirePrincipal(request: HttpServletRequest): Principal {
    val principal = request.getAttribute(PRINCIPAL_ATTR) as? Principal
    return principal ?: throw ProxyError.noApiKeyPassed()
}

fun requireAdmin(request: HttpServletRequest): Principal {
    val principal = requirePrincipal(request)
    if (!principal.isProxyAdmin) {
        throw ProxyError.forbidden("You do not have permission to access this resource. Require role(s): proxy_admin")
    }
    return principal
}

fun touchedBy(principal: Principal): String =
    principal.userId ?: "default_user_id"
