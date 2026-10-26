package ai.litellm.backend.web

import ai.litellm.backend.auth.PRINCIPAL_ATTR
import ai.litellm.backend.auth.CallerResolver
import ai.litellm.backend.config.YamlConfigProvider
import com.fasterxml.jackson.databind.ObjectMapper
import jakarta.servlet.FilterChain
import jakarta.servlet.http.HttpServletRequest
import jakarta.servlet.http.HttpServletResponse
import org.springframework.stereotype.Component
import org.springframework.web.filter.OncePerRequestFilter

@Component
class AuthFilter(
    private val resolver: CallerResolver,
    private val yaml: YamlConfigProvider,
    private val objectMapper: ObjectMapper,
) : OncePerRequestFilter() {

    private val publicExact = setOf(
        "/", "/docs", "/docs/oauth2-redirect", "/openapi.json", "/redoc", "/robots.txt",
        "/favicon.ico", "/login", "/v2/login", "/v3/login", "/fallback/login",
        "/get_logo_url", "/get_favicon", "/get_image", "/sso_settings", "/metrics", "/error",
    )

    private val publicPrefixes = listOf(
        "/health", "/sso", "/onboarding", "/ui_discovery", "/public", "/swagger", "/.well-known", "/static",
    )

    override fun doFilterInternal(
        request: HttpServletRequest,
        response: HttpServletResponse,
        filterChain: FilterChain,
    ) {
        val path = request.requestURI
        if (publicExact.contains(path) || publicPrefixes.any { path.startsWith(it) }) {
            filterChain.doFilter(request, response)
            return
        }
        val headerName = yaml.yamlConfig.config.keyHeaderName()
        val rawHeader = request.getHeader(headerName)
        val headerKey = rawHeader
            ?.takeIf { it.isNotBlank() }
            ?.let { if (it.lowercase().startsWith("bearer ")) it.substring(7).trim() else it }
        try {
            val principal = resolver.resolve(headerKey)
            request.setAttribute(PRINCIPAL_ATTR, principal)
            filterChain.doFilter(request, response)
        } catch (e: ProxyError) {
            response.status = e.code
            response.contentType = "application/json"
            response.writer.write(
                objectMapper.writeValueAsString(
                    ErrorEnvelope(ErrorDetail(e.errorMessage, e.type, e.param, e.code.toString()))
                )
            )
        }
    }
}
