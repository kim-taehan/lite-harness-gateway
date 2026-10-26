package ai.litellm.backend.web

import com.fasterxml.jackson.databind.node.TextNode
import jakarta.persistence.EntityManager
import org.springframework.http.MediaType
import org.springframework.http.ResponseEntity
import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.RestController
import java.util.LinkedHashMap

@RestController
class HealthController(private val entityManager: EntityManager) {
    @GetMapping("/health/liveliness", produces = [MediaType.APPLICATION_JSON_VALUE])
    fun liveliness(): TextNode = TextNode("I'm alive!")

    @GetMapping("/health/readiness", produces = [MediaType.APPLICATION_JSON_VALUE])
    fun readiness(): ResponseEntity<Map<String, String>> {
        val db = try {
            entityManager.createNativeQuery("select 1").setMaxResults(1).singleResult
            "connected"
        } catch (e: Exception) {
            "disconnected"
        }
        val body = LinkedHashMap<String, String>().apply {
            put("status", if (db == "connected") "healthy" else "unhealthy")
            put("db", db)
        }
        return ResponseEntity
            .status(if (db == "connected") 200 else 503)
            .body(body)
    }
}
