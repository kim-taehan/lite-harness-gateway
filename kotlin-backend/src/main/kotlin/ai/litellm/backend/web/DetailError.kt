package ai.litellm.backend.web

class DetailError(val status: Int, val detail: Any?) : RuntimeException()
