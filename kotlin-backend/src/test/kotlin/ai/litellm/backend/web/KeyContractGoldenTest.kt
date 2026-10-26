package ai.litellm.backend.web

import ai.litellm.backend.LitellmBackendApplication
import com.fasterxml.jackson.databind.JsonNode
import com.fasterxml.jackson.databind.ObjectMapper
import org.junit.jupiter.api.Test
import org.springframework.beans.factory.annotation.Autowired
import org.springframework.boot.test.context.SpringBootTest
import org.springframework.boot.test.web.client.TestRestTemplate
import org.springframework.http.HttpEntity
import org.springframework.http.HttpHeaders
import org.springframework.http.HttpMethod
import org.springframework.http.MediaType
import java.security.SecureRandom
import kotlin.test.assertEquals

@SpringBootTest(
    classes = [LitellmBackendApplication::class],
    webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
    properties = [
        "litellm.master-key=sk-golden-contract-master",
        "litellm.ui-username=admin",
        "litellm.ui-password=admin-pass-123",
    ],
)
class KeyContractGoldenTest {
    @Autowired
    lateinit var rest: TestRestTemplate

    private val mapper = ObjectMapper()

    private val generateOrder = listOf(
        "key_alias", "duration", "models", "spend", "max_budget", "user_id", "team_id", "agent_id",
        "max_parallel_requests", "metadata", "tpm_limit", "rpm_limit", "budget_duration", "budget_limits",
        "allowed_cache_controls", "config", "permissions", "model_max_budget", "budget_fallbacks",
        "model_rpm_limit", "model_tpm_limit", "mcp_rpm_limit", "tag_rpm_limit", "guardrails", "policies",
        "prompts", "blocked", "aliases", "object_permission", "key", "tpd_limit",
        "default_estimated_output_tokens", "default_estimated_output_tokens_per_model", "budget_id",
        "end_user_budget_id", "tags", "disable_global_guardrails", "enable_prompt_caching",
        "throttle_on_budget_exceeded", "enforced_params", "allowed_routes", "allowed_passthrough_routes",
        "denied_passthrough_routes", "allowed_vector_store_indexes", "rpm_limit_type", "tpm_limit_type",
        "router_settings", "access_group_ids", "key_name", "key_type", "expires", "token_id",
        "organization_id", "project_id", "litellm_budget_table", "token", "created_by", "updated_by",
        "created_at", "updated_at",
    )

    private val infoOrder = listOf(
        "key_name", "key_alias", "soft_budget_cooldown", "spend", "total_spend", "expires", "models",
        "aliases", "config", "router_settings", "user_id", "team_id", "agent_id", "project_id", "permissions",
        "max_parallel_requests", "metadata", "blocked", "tpm_limit", "rpm_limit", "tpd_limit", "max_budget",
        "budget_duration", "budget_reset_at", "allowed_cache_controls", "allowed_routes", "key_type",
        "policies", "access_group_ids", "model_spend", "model_max_budget", "budget_fallbacks", "budget_id",
        "organization_id", "object_permission_id", "created_at", "created_by", "updated_at", "updated_by",
        "settings_updated_at", "last_active", "rotation_count", "auto_rotate", "rotation_interval",
        "last_rotation_at", "key_rotation_at", "budget_limits", "litellm_budget_table",
        "litellm_organization_table", "litellm_project_table", "object_permission", "jwt_key_mappings", "status",
    )

    private val updateOrder = listOf(
        "key", "token", "key_name", "key_alias", "soft_budget_cooldown", "spend", "total_spend", "expires",
        "models", "aliases", "config", "router_settings", "user_id", "team_id", "agent_id", "project_id",
        "permissions", "max_parallel_requests", "metadata", "blocked", "tpm_limit", "rpm_limit", "tpd_limit",
        "max_budget", "budget_duration", "budget_reset_at", "allowed_cache_controls", "allowed_routes",
        "key_type", "policies", "access_group_ids", "model_spend", "model_max_budget", "budget_fallbacks",
        "budget_id", "organization_id", "object_permission_id", "created_at", "created_by", "updated_at",
        "updated_by", "settings_updated_at", "last_active", "rotation_count", "auto_rotate", "rotation_interval",
        "last_rotation_at", "key_rotation_at", "budget_limits", "litellm_budget_table",
        "litellm_organization_table", "litellm_project_table", "object_permission", "jwt_key_mappings",
    )

    private val blockOrder = listOf(
        "token", "key_name", "key_alias", "spend", "total_spend", "max_budget", "expires", "models",
        "aliases", "config", "user_id", "team_id", "agent_id", "project_id", "max_parallel_requests",
        "metadata", "tpm_limit", "rpm_limit", "tpd_limit", "budget_duration", "budget_reset_at",
        "allowed_cache_controls", "allowed_routes", "key_type", "permissions", "model_spend", "model_max_budget",
        "budget_fallbacks", "soft_budget_cooldown", "blocked", "litellm_budget_table", "budget_id", "org_id",
        "created_at", "created_by", "updated_at", "updated_by", "settings_updated_at", "last_active",
        "object_permission_id", "object_permission", "access_group_ids", "rotation_count", "auto_rotate",
        "rotation_interval", "last_rotation_at", "key_rotation_at", "router_settings", "budget_limits",
    )

    private val unblockOrder = listOf(
        "token", "key_name", "key_alias", "soft_budget_cooldown", "spend", "total_spend", "expires", "models",
        "aliases", "config", "router_settings", "user_id", "team_id", "agent_id", "project_id", "permissions",
        "max_parallel_requests", "metadata", "blocked", "tpm_limit", "rpm_limit", "tpd_limit", "max_budget",
        "budget_duration", "budget_reset_at", "allowed_cache_controls", "allowed_routes", "key_type",
        "policies", "access_group_ids", "model_spend", "model_max_budget", "budget_fallbacks", "budget_id",
        "organization_id", "object_permission_id", "created_at", "created_by", "updated_at", "updated_by",
        "settings_updated_at", "last_active", "rotation_count", "auto_rotate", "rotation_interval",
        "last_rotation_at", "key_rotation_at", "budget_limits", "litellm_budget_table",
        "litellm_organization_table", "litellm_project_table", "object_permission", "jwt_key_mappings",
    )

    private val listViewOrder = listOf(
        "token", "key_name", "key_alias", "spend", "total_spend", "max_budget", "expires", "models",
        "aliases", "config", "user_id", "team_id", "agent_id", "project_id", "max_parallel_requests",
        "metadata", "tpm_limit", "rpm_limit", "tpd_limit", "budget_duration", "budget_reset_at",
        "allowed_cache_controls", "allowed_routes", "key_type", "permissions", "model_spend", "model_max_budget",
        "budget_fallbacks", "soft_budget_cooldown", "blocked", "litellm_budget_table", "budget_id", "org_id",
        "created_at", "created_by", "updated_at", "updated_by", "settings_updated_at", "last_active",
        "object_permission_id", "object_permission", "access_group_ids", "rotation_count", "auto_rotate",
        "rotation_interval", "last_rotation_at", "key_rotation_at", "router_settings", "budget_limits",
        "team_spend", "team_alias", "team_tpm_limit", "team_rpm_limit", "team_tpd_limit", "team_max_budget",
        "team_soft_budget", "team_model_max_budget", "team_models", "team_blocked", "soft_budget",
        "team_model_aliases", "team_member", "team_metadata", "team_object_permission_id", "team_member_spend",
        "team_member_tpm_limit", "team_member_rpm_limit", "end_user_id", "end_user_tpm_limit",
        "end_user_rpm_limit", "end_user_tpd_limit", "end_user_max_budget", "end_user_model_max_budget",
        "organization_alias", "organization_max_budget", "organization_tpm_limit", "organization_rpm_limit",
        "organization_metadata", "project_alias", "project_metadata", "last_refreshed_at", "api_key",
        "user_role", "allowed_model_region", "parent_otel_span", "rpm_limit_per_model", "tpm_limit_per_model",
        "user_tpm_limit", "user_rpm_limit", "user_email", "user_spend", "user_max_budget",
        "user_model_max_budget", "request_route", "is_session_token", "user", "created_by_user",
        "end_user_object_permission", "team_object_permission", "jwt_claims",
    )

    private val deletedInfoOrder = listOf(
        "key_name", "key_alias", "spend", "total_spend", "max_budget", "expires", "models", "aliases",
        "config", "user_id", "team_id", "agent_id", "project_id", "max_parallel_requests", "metadata",
        "tpm_limit", "rpm_limit", "tpd_limit", "budget_duration", "budget_reset_at", "allowed_cache_controls",
        "allowed_routes", "key_type", "permissions", "model_spend", "model_max_budget", "budget_fallbacks",
        "soft_budget_cooldown", "blocked", "litellm_budget_table", "budget_id", "org_id", "created_at",
        "created_by", "updated_at", "updated_by", "settings_updated_at", "last_active", "object_permission_id",
        "object_permission", "access_group_ids", "rotation_count", "auto_rotate", "rotation_interval",
        "last_rotation_at", "key_rotation_at", "router_settings", "budget_limits", "id", "organization_id",
        "deleted_at", "deleted_by", "deleted_by_api_key", "litellm_changed_by", "status",
    )

    private val zedRegex = Regex("""^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{6})?Z$""")
    private val offsetRegex = Regex("""^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{6})?\+00:00$""")

    private fun orderOf(node: JsonNode): List<String> {
        val names = ArrayList<String>()
        val it = node.fields()
        while (it.hasNext()) names.add(it.next().key)
        return names
    }

    private fun postJson(path: String, body: String): Pair<Int, JsonNode> {
        val headers = HttpHeaders().apply {
            contentType = MediaType.APPLICATION_JSON
            setBearerAuth("sk-golden-contract-master")
        }
        val resp = rest.exchange(path, HttpMethod.POST, HttpEntity(body, headers), String::class.java)
        return resp.statusCode.value() to mapper.readTree(resp.body)
    }

    private fun get(path: String): Pair<Int, JsonNode> {
        val headers = HttpHeaders().apply { setBearerAuth("sk-golden-contract-master") }
        val resp = rest.exchange(path, HttpMethod.GET, HttpEntity<String?>(null, headers), String::class.java)
        return resp.statusCode.value() to mapper.readTree(resp.body)
    }

    @Test
    fun `key lifecycle matches oracle contract`() {
        val alias = "golden-${SecureRandom().nextLong(100000000L)}"
        val (genStatus, gen) = postJson(
            "/key/generate",
            """{"key_alias":"$alias","models":["devstral"],"max_budget":5,"duration":"7d"}""",
        )
        assertEquals(200, genStatus)
        assertEquals(generateOrder, orderOf(gen))
        val rawKey = gen["key"].asText()
        assertEquals(25, rawKey.length)
        assertEquals("sk-..." + rawKey.takeLast(4), gen["key_name"].asText())
        assertEquals(gen["token"].asText(), gen["token_id"].asText())
        assertEquals("default", gen["key_type"].asText())
        assertEquals(true, gen["duration"].isNull())
        assertEquals(true, gen["policies"].isNull())
        assertEquals(5.0, gen["max_budget"].asDouble())
        assertEquals(0.0, gen["spend"].asDouble())
        assertEquals("default_user_id", gen["created_by"].asText())
        assertTrue(generatedAtIsZoned(gen["created_at"].asText()))
        assertTrue(generatedAtIsZoned(gen["expires"].asText()))
        assertEquals(mapper.createObjectNode(), gen["router_settings"]["model_group_alias"])
        assertEquals(mapper.createObjectNode(), gen["metadata"])

        val (infoStatus, info) = get("/key/info?key=$rawKey")
        assertEquals(200, infoStatus)
        assertEquals(rawKey, info["key"].asText())
        assertEquals(infoOrder, orderOf(info["info"]))
        assertEquals("active", info["info"]["status"].asText())
        assertTrue(offsetRegex.matches(info["info"]["created_at"].asText()))

        val (updStatus, upd) = postJson("/key/update", """{"key":"$rawKey","max_budget":9}""")
        assertEquals(200, updStatus)
        assertEquals(updateOrder, orderOf(upd))
        assertEquals(rawKey, upd["key"].asText())
        assertEquals(9.0, upd["max_budget"].asDouble())
        assertTrue(offsetRegex.matches(upd["settings_updated_at"].asText()))

        val (blkStatus, blk) = postJson("/key/block", """{"key":"$rawKey"}""")
        assertEquals(200, blkStatus)
        assertEquals(blockOrder, orderOf(blk))
        assertEquals(true, blk["blocked"].asBoolean())
        assertTrue(zedRegex.matches(blk["settings_updated_at"].asText()))

        val (_, blkInfo) = get("/key/info?key=$rawKey")
        assertEquals("revoked", blkInfo["info"]["status"].asText())

        val (unStatus, unbl) = postJson("/key/unblock", """{"key":"$rawKey"}""")
        assertEquals(200, unStatus)
        assertEquals(unblockOrder, orderOf(unbl))
        assertEquals(false, unbl["blocked"].asBoolean())

        val (listStatus, list) = get("/key/list?key_alias=$alias&return_full_object=true")
        assertEquals(200, listStatus)
        assertEquals(1, list["keys"].size())
        assertEquals(listViewOrder, orderOf(list["keys"][0]))
        assertEquals(false, list["keys"][0]["team_blocked"].asBoolean())
        assertEquals(false, list["keys"][0]["is_session_token"].asBoolean())
        assertEquals(0, list["keys"][0]["team_models"].size())

        val (hashStatus, hashList) = get("/key/list?key_alias=$alias")
        assertEquals(200, hashStatus)
        assertEquals(1, hashList["keys"].size())
        assertEquals(upd["token"].asText(), hashList["keys"][0].asText())
        assertEquals(1, hashList["total_count"].asInt())

        val (delStatus, del) = postJson("/key/delete", """{"keys":["$rawKey"]}""")
        assertEquals(200, delStatus)
        assertEquals(rawKey, del["deleted_keys"][0].asText())

        val (delInfoStatus, delInfo) = get("/key/info?key=$rawKey")
        assertEquals(200, delInfoStatus)
        assertEquals(deletedInfoOrder, orderOf(delInfo["info"]))
        assertEquals("deleted", delInfo["info"]["status"].asText())
        assertTrue(offsetRegex.matches(delInfo["info"]["deleted_at"].asText()))
        assertEquals(true, delInfo["info"]["org_id"].isNull())
    }

    @Test
    fun `key error contracts match oracle`() {
        val (s1, b1) = postJson("/key/generate", """{"key":"nope"}""")
        assertEquals(400, s1)
        assertEquals("internal_server_error", b1["error"]["type"].asText())
        assertEquals(
            """{'error': "Invalid key format. LiteLLM Virtual Key must start with 'sk-'. Received: ****"}""",
            b1["error"]["message"].asText(),
        )

        val (s2, b2) = postJson("/key/generate", """{"key":"sk-abc"}""")
        assertEquals(400, s2)
        assertEquals(
            "{'error': 'Invalid key format. LiteLLM Virtual Key must be at least 16 characters long.'}",
            b2["error"]["message"].asText(),
        )

        val (s3, b3) = postJson("/key/block", """{}""")
        assertEquals(422, s3)
        assertEquals("missing", b3["detail"][0]["type"].asText())

        val (s4, b4) = get("/key/info?key=sk-doesnotexist000000")
        assertEquals(404, s4)
        assertEquals("Key not found in database", b4["error"]["message"].asText())
        assertEquals("not_found_error", b4["error"]["type"].asText())

        val (s5, b5) = postJson("/key/block", """{"key":"sk-doesnotexist000000"}""")
        assertEquals(404, s5)
        assertEquals("Key not found.", b5["error"]["message"].asText())
    }

    private fun generatedAtIsZoned(text: String): Boolean = zedRegex.matches(text)

    private fun assertTrue(condition: Boolean) {
        if (!condition) throw AssertionError("expected true")
    }
}
