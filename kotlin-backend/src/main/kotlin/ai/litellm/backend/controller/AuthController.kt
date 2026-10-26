package ai.litellm.backend.controller

import ai.litellm.backend.auth.LoginOutcome
import ai.litellm.backend.auth.LoginService
import ai.litellm.backend.auth.LogoutOutcome
import ai.litellm.backend.auth.SessionLogoutService
import ai.litellm.backend.auth.requirePrincipal
import jakarta.servlet.http.HttpServletRequest
import org.springframework.http.HttpHeaders
import org.springframework.http.MediaType
import org.springframework.http.ResponseEntity
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RequestParam
import org.springframework.web.bind.annotation.RestController
import java.net.URI

data class LoginRequest(
    val username: String? = null,
    val password: String? = null,
)

@RestController
class AuthController(
    private val loginService: LoginService,
    private val sessionLogoutService: SessionLogoutService,
) {

    @PostMapping("/login", consumes = [MediaType.APPLICATION_FORM_URLENCODED_VALUE])
    fun loginForm(
        @RequestParam username: String,
        @RequestParam password: String,
        request: HttpServletRequest,
    ): ResponseEntity<Void> =
        issueSession(loginService.login(username, password), request)

    @PostMapping("/v2/login", consumes = [MediaType.APPLICATION_JSON_VALUE])
    fun loginV2(@RequestBody body: LoginRequest, request: HttpServletRequest): ResponseEntity<Void> =
        issueSession(loginService.login(body.username ?: "", body.password ?: ""), request)

    @PostMapping("/v3/login", consumes = [MediaType.APPLICATION_JSON_VALUE])
    fun loginV3(@RequestBody body: LoginRequest, request: HttpServletRequest): ResponseEntity<Void> =
        issueSession(loginService.login(body.username ?: "", body.password ?: ""), request)

    @PostMapping("/session/logout")
    fun sessionLogout(request: HttpServletRequest): ResponseEntity<*> {
        val principal = requirePrincipal(request)
        return when (val outcome = sessionLogoutService.revoke(principal)) {
            is LogoutOutcome.Forbidden ->
                ResponseEntity.status(403).body(mapOf("detail" to mapOf("error" to outcome.message)))
            is LogoutOutcome.Revoked ->
                ResponseEntity
                    .status(200)
                    .header(HttpHeaders.SET_COOKIE, "token=; Path=/; SameSite=lax; Max-Age=0")
                    .body(mapOf("message" to if (outcome.wasActive) "Session revoked." else "Session already revoked."))
        }
    }

    private fun issueSession(outcome: LoginOutcome, request: HttpServletRequest): ResponseEntity<Void> =
        respondWithRedirect(request)
            .header(HttpHeaders.SET_COOKIE, "token=${outcome.jwt}; Path=/; SameSite=lax")
            .build()

    private fun respondWithRedirect(request: HttpServletRequest): ResponseEntity.BodyBuilder {
        val base = System.getenv("PROXY_BASE_URL")?.trimEnd('/')
            ?: "${request.scheme}://${request.serverName}:${request.serverPort}"
        return ResponseEntity
            .status(303)
            .location(URI.create("$base/ui?login=success"))
    }
}
