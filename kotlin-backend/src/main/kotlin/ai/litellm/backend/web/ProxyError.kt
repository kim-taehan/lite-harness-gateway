package ai.litellm.backend.web

class ProxyError(
    val errorMessage: String,
    val type: String,
    val param: Any?,
    val code: Int,
) : RuntimeException(errorMessage) {
    companion object {
        fun noApiKeyPassed(): ProxyError =
            ProxyError("Authentication Error, No api key passed in.", "auth_error", "None", 401)

        fun tokenNotFound(receivedKey: String, keyHash: String): ProxyError =
            ProxyError(
                "Authentication Error, Invalid proxy server token passed. Received API Key = " +
                    HashingAbbr.abbreviate(receivedKey) +
                    ", Key Hash (Token) =" + keyHash +
                    ". Unable to find token in cache or `LiteLLM_VerificationTokenTable`",
                "token_not_found_in_db",
                "key",
                401,
            )

        fun invalidCredentials(message: String): ProxyError =
            ProxyError(message, "auth_error", "invalid_credentials", 401)

        fun virtualKeyExpected(received: String): ProxyError {
            val masked =
                if (received.length > 8) received.substring(0, 4) + "****" + received.substring(received.length - 4)
                else "****"
            val hint =
                if (received.startsWith("eyJ") && received.count { it == '.' } == 2) {
                    " This key has the structure of a JWT, but JWT auth is not enabled on this proxy, so it was treated as a virtual key. " +
                        "Set `enable_jwt_auth: true` under `general_settings` in your proxy config to authenticate with JWTs."
                } else {
                    ""
                }
            return ProxyError(
                "LiteLLM Virtual Key expected. Received=$masked, expected to start with 'sk-'.$hint",
                "auth_error",
                "None",
                401,
            )
        }

        fun forbidden(detail: String): ProxyError =
            ProxyError(detail, "auth_error", "None", 403)

        fun badRequest(detail: Any): ProxyError =
            ProxyError(PyRepr.of(detail), "internal_server_error", null, 400)
    }
}

private object HashingAbbr {
    fun abbreviate(apiKey: String): String =
        ai.litellm.backend.auth.Hashing.abbreviateApiKey(apiKey)
}

object PyRepr {
    fun of(detail: Any): String = when (detail) {
        is Map<*, *> -> detail.entries.joinToString(prefix = "{", postfix = "}", separator = ", ") { (k, v) ->
            "${pyString(k.toString())}: ${reprValue(v)}"
        }
        else -> reprValue(detail)
    }

    fun reprValue(value: Any?): String = when (value) {
        null -> "None"
        is String -> pyString(value)
        is Boolean -> value.toString().replaceFirstChar { it.uppercase() }
        is Double -> value.toString().let { if (it.contains("f") || it.contains(".")) it else "$it.0" }
        is Int -> value.toString()
        is Map<*, *> -> of(value)
        is List<*> -> value.joinToString(prefix = "[", postfix = "]") { reprValue(it) }
        else -> pyString(value.toString())
    }

    private fun pyString(s: String): String {
        val escaped = if (s.contains('\'') && !s.contains('\"')) {
            s.replace("\\", "\\\\").replace("\"", "\\\"")
        } else {
            s.replace("\\", "\\\\").replace("'", "\\'")
        }
        val useDouble = s.contains('\'') && !s.contains('\"')
        return if (useDouble) "\"$escaped\"" else "'$escaped'"
    }
}
