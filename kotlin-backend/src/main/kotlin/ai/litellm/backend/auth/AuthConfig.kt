package ai.litellm.backend.auth

import ai.litellm.backend.config.BackendProperties
import org.springframework.context.annotation.Bean
import org.springframework.context.annotation.Configuration

@Configuration
class AuthConfig {
    @Bean
    fun uiSessionJwt(properties: BackendProperties): UiSessionJwt =
        UiSessionJwt(properties.masterKey.ifBlank { "sk-litellm-default-master-key" })
}
