package ai.litellm.backend.web

import com.fasterxml.jackson.databind.node.TextNode
import org.springframework.http.CacheControl
import org.springframework.http.HttpStatus
import org.springframework.http.MediaType
import org.springframework.http.ResponseEntity
import org.springframework.web.bind.annotation.ExceptionHandler
import org.springframework.web.bind.annotation.RestControllerAdvice
import org.springframework.http.converter.HttpMessageNotReadableException
import org.springframework.web.bind.MethodArgumentNotValidException

data class ErrorDetail(
    val message: String,
    val type: String,
    val param: Any?,
    val code: String,
)

data class ErrorEnvelope(val error: ErrorDetail)

@RestControllerAdvice
class ProxyExceptionHandler {
    @ExceptionHandler(ProxyError::class)
    fun handleProxyError(e: ProxyError): ResponseEntity<ErrorEnvelope> =
        ResponseEntity
            .status(e.code)
            .body(ErrorEnvelope(ErrorDetail(e.errorMessage, e.type, e.param, e.code.toString())))

    @ExceptionHandler(DetailError::class)
    fun handleDetailError(e: DetailError): ResponseEntity<Map<String, Any?>> =
        ResponseEntity
            .status(e.status)
            .body(mapOf("detail" to e.detail))

    @ExceptionHandler(MethodArgumentNotValidException::class)
    fun handleValidation(e: MethodArgumentNotValidException): ResponseEntity<ErrorEnvelope> {
        val message = e.bindingResult.fieldErrors.joinToString(", ") { "${it.field}: ${it.defaultMessage}" }
        return ResponseEntity
            .status(HttpStatus.BAD_REQUEST)
            .body(ErrorEnvelope(ErrorDetail(pyReprDetail(message), "internal_server_error", null, "400")))
    }

    @ExceptionHandler(HttpMessageNotReadableException::class)
    fun handleUnreadable(e: HttpMessageNotReadableException): ResponseEntity<ErrorEnvelope> =
        ResponseEntity
            .status(HttpStatus.BAD_REQUEST)
            .body(ErrorEnvelope(ErrorDetail("Invalid JSON body", "internal_server_error", null, "400")))

    private fun pyReprDetail(message: String): String = PyRepr.reprValue(message)
}
