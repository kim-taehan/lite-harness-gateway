package ai.litellm.backend.web

import jakarta.servlet.http.HttpServletRequest
import org.springframework.boot.web.servlet.error.ErrorController
import org.springframework.http.HttpStatus
import org.springframework.http.ResponseEntity
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.RestController

@RestController
class ProxyErrorController : ErrorController {
    @RequestMapping("/error")
    fun handle(errorRequest: HttpServletRequest): ResponseEntity<Any> {
        val statusAttr =
            errorRequest.getAttribute("jakarta.servlet.error.status_code")
                ?: errorRequest.getAttribute("jakarta.servlet.error.status")
        val status = (statusAttr as? Number)?.toInt() ?: HttpStatus.OK.value()
        return when (status) {
            400 -> ResponseEntity.status(400).body(mapOf("detail" to "Bad Request"))
            403 -> ResponseEntity.status(403).body(mapOf("detail" to "Forbidden"))
            404 -> ResponseEntity.status(404).body(mapOf("detail" to "Not Found"))
            405 -> ResponseEntity.status(405).body(mapOf("detail" to "Method Not Allowed"))
            in 400..499 -> ResponseEntity.status(status).body(mapOf("detail" to "Error $status"))
            else -> ResponseEntity
                .status(500)
                .body(mapOf("error" to ErrorDetail("Internal Server Error", "internal_server_error", null, "500")))
        }
    }
}
