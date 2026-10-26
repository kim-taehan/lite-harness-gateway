package ai.litellm.backend.config

import com.fasterxml.jackson.core.JsonGenerator
import com.fasterxml.jackson.core.JsonParser
import com.fasterxml.jackson.databind.DeserializationContext
import com.fasterxml.jackson.databind.JsonDeserializer
import com.fasterxml.jackson.databind.JsonSerializer
import com.fasterxml.jackson.databind.PropertyNamingStrategies
import com.fasterxml.jackson.databind.SerializationFeature
import com.fasterxml.jackson.databind.SerializerProvider
import com.fasterxml.jackson.datatype.jsr310.deser.LocalDateDeserializer
import com.fasterxml.jackson.datatype.jsr310.ser.LocalDateSerializer
import org.springframework.boot.autoconfigure.jackson.Jackson2ObjectMapperBuilderCustomizer
import org.springframework.context.annotation.Bean
import org.springframework.context.annotation.Configuration
import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter

object TimeFormats {
    val ZONED: DateTimeFormatter =
        DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss[.SSSSSS]'Z'").withZone(ZoneOffset.UTC)
    val NAIVE: DateTimeFormatter = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss")
    val NAIVE_FLEXIBLE: DateTimeFormatter = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss[.SSSSSS]")

    fun parseInstant(text: String): Instant =
        if (text.endsWith("Z")) Instant.parse(text)
        else LocalDateTime.parse(text, NAIVE_FLEXIBLE).atZone(ZoneOffset.UTC).toInstant()
}

class InstantAsStringSerializer : JsonSerializer<Instant>() {
    override fun serialize(value: Instant, gen: JsonGenerator, provider: SerializerProvider) {
        gen.writeString(TimeFormats.ZONED.format(value))
    }
}

class InstantAsStringDeserializer : JsonDeserializer<Instant>() {
    override fun deserialize(content: JsonParser, ctx: DeserializationContext): Instant =
        TimeFormats.parseInstant(content.text.trim())
}

class LocalDateTimeAsNaiveSerializer : JsonSerializer<LocalDateTime>() {
    override fun serialize(value: LocalDateTime, gen: JsonGenerator, provider: SerializerProvider) {
        gen.writeString(TimeFormats.NAIVE.format(value))
    }
}

class LocalDateTimeAsNaiveDeserializer : JsonDeserializer<LocalDateTime>() {
    override fun deserialize(content: JsonParser, ctx: DeserializationContext): LocalDateTime =
        LocalDateTime.parse(content.text.trim(), TimeFormats.NAIVE_FLEXIBLE)
}

@Configuration
class JacksonConfig {
    @Bean
    fun objectMapperCustomizer(): Jackson2ObjectMapperBuilderCustomizer =
        Jackson2ObjectMapperBuilderCustomizer { builder ->
            builder.propertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE)
            builder.featuresToDisable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS)
            builder.serializerByType(Instant::class.java, InstantAsStringSerializer())
            builder.deserializerByType(Instant::class.java, InstantAsStringDeserializer())
            builder.serializerByType(LocalDateTime::class.java, LocalDateTimeAsNaiveSerializer())
            builder.deserializerByType(LocalDateTime::class.java, LocalDateTimeAsNaiveDeserializer())
            builder.serializerByType(LocalDate::class.java, LocalDateSerializer(TimeFormats.NAIVE))
            builder.deserializerByType(LocalDate::class.java, LocalDateDeserializer(TimeFormats.NAIVE))
        }
}
