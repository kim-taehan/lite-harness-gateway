package ai.litellm.backend.config

import org.slf4j.LoggerFactory
import org.springframework.core.io.FileSystemResource
import org.springframework.stereotype.Component
import java.io.File

data class ModelEntry(
    val modelName: String,
    val litellmParams: Map<String, Any?>,
    val modelInfo: Map<String, Any?>,
)

data class ProxyConfig(
    val modelList: List<ModelEntry>,
    val litellmSettings: Map<String, Any?>,
    val generalSettings: Map<String, Any?>,
) {
    val configMasterKey: String?
        get() = generalSettings["master_key"] as? String

    fun keyHeaderName(): String =
        generalSettings["litellm_key_header_name"] as? String ?: "Authorization"
}

data class LiteLlmYamlConfig(
    val models: List<ModelEntry>,
    val litellmSettings: Map<String, Any?>,
    val generalSettings: Map<String, Any?>,
) {
    val config: ProxyConfig
        get() = ProxyConfig(models, litellmSettings, generalSettings)

    companion object {
        val EMPTY = LiteLlmYamlConfig(emptyList(), emptyMap(), emptyMap())

        fun load(path: String): LiteLlmYamlConfig {
            val file = File(path)
            if (!file.isFile) {
                log.info("config.yaml not found at $path, running with empty config")
                return EMPTY
            }
            return try {
                parse(FileSystemResource(file).inputStream)
            } catch (e: Exception) {
                log.warn("failed to parse $path: ${e.message}, running with empty config")
                EMPTY
            }
        }

        @Suppress("UNCHECKED_CAST")
        private fun parse(inputStream: java.io.InputStream): LiteLlmYamlConfig {
            val yaml = org.yaml.snakeyaml.Yaml()
            val loaded: Any? = yaml.load(inputStream.bufferedReader())
            val root: Map<String, Any?> = (loaded as? Map<String, Any?>) ?: emptyMap()
            @Suppress("UNCHECKED_CAST")
            val models = (root["model_list"] as? List<Map<String, Any?>>)?.mapNotNull { entry ->
                val name = entry["model_name"] as? String ?: return@mapNotNull null
                @Suppress("UNCHECKED_CAST")
                val params = (entry["litellm_params"] as? Map<String, Any?>) ?: emptyMap()
                @Suppress("UNCHECKED_CAST")
                val info = (entry["model_info"] as? Map<String, Any?>) ?: emptyMap()
                ModelEntry(name, params, info)
            } ?: emptyList()
            @Suppress("UNCHECKED_CAST")
            val settings = (root["litellm_settings"] as? Map<String, Any?>) ?: emptyMap()
            @Suppress("UNCHECKED_CAST")
            val general = (root["general_settings"] as? Map<String, Any?>) ?: emptyMap()
            return LiteLlmYamlConfig(models, settings, general)
        }

        private val log = LoggerFactory.getLogger(LiteLlmYamlConfig::class.java)
    }
}

@Component
class YamlConfigProvider(properties: BackendProperties) {
    val yamlConfig: LiteLlmYamlConfig = LiteLlmYamlConfig.load(properties.configYamlPath)
}
