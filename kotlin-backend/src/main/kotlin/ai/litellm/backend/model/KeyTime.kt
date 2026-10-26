package ai.litellm.backend.model

import java.time.Instant
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter

object KeyTime {

    private val SECONDS: DateTimeFormatter = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss").withZone(ZoneOffset.UTC)
    private val MICROS: DateTimeFormatter = DateTimeFormatter.ofPattern("SSSSSS").withZone(ZoneOffset.UTC)

    fun fmtZ(value: Instant?): String? = value?.let { fmt(it, "Z") }

    fun fmtOffset(value: Instant?): String? = value?.let { fmt(it, "+00:00") }

    private fun fmt(value: Instant, suffix: String): String {
        val base = SECONDS.format(value)
        return if (value.nano > 0) "$base.${MICROS.format(value)}$suffix" else "$base$suffix"
    }
}
