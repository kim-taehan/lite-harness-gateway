package ai.litellm.backend.auth

object DurationParser {
    private data class Unit(val suffix: String, val seconds: Long)

    private val units = listOf(
        Unit("s", 1),
        Unit("m", 60),
        Unit("h", 3600),
        Unit("d", 86400),
        Unit("mo", 30L * 86400),
        Unit("y", 365L * 86400),
    )

    fun durationInSeconds(duration: String): Long {
        val text = duration.trim().lowercase()
        val match = Regex("^(\\d+)([a-z]+)$").find(text)
            ?: throw IllegalArgumentException("Invalid duration format: $duration")
        val value = match.groupValues[1].toLong()
        val unit = units.firstOrNull { it.suffix == match.groupValues[2] }
            ?: throw IllegalArgumentException("Unsupported duration unit in: $duration")
        return value * unit.seconds
    }
}
