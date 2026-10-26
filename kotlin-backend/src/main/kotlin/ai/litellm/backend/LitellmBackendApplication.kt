package ai.litellm.backend

import org.springframework.boot.autoconfigure.SpringBootApplication
import org.springframework.boot.context.properties.ConfigurationPropertiesScan
import org.springframework.boot.runApplication

@SpringBootApplication
@ConfigurationPropertiesScan
class LitellmBackendApplication

fun main(args: Array<String>) {
    runApplication<LitellmBackendApplication>(*args)
}
