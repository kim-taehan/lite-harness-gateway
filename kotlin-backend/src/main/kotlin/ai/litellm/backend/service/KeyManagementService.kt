package ai.litellm.backend.service

import ai.litellm.backend.auth.Hashing
import ai.litellm.backend.auth.Principal
import ai.litellm.backend.auth.deletedRecordOf
import ai.litellm.backend.auth.touchedBy
import ai.litellm.backend.domain.VerificationTokenEntity
import ai.litellm.backend.model.KeyViews
import ai.litellm.backend.repository.DeletedTokenRepository
import ai.litellm.backend.repository.VerificationTokenRepository
import ai.litellm.backend.web.DetailError
import ai.litellm.backend.web.ProxyError
import com.fasterxml.jackson.databind.JsonNode
import com.fasterxml.jackson.databind.node.JsonNodeFactory
import org.springframework.stereotype.Service
import java.time.Duration
import java.time.Instant

data class KeyGenerateRequest(
    val key: String? = null,
    val keyAlias: String? = null,
    val duration: String? = null,
    val models: List<String>? = null,
    val maxBudget: Double? = null,
    val userId: String? = null,
    val teamId: String? = null,
    val agentId: String? = null,
    val projectId: String? = null,
    val organizationId: String? = null,
    val keyType: String? = null,
    val maxParallelRequests: Int? = null,
    val metadata: JsonNode? = null,
    val tpmLimit: Long? = null,
    val rpmLimit: Long? = null,
    val tpdLimit: Long? = null,
    val budgetDuration: String? = null,
    val allowedCacheControls: List<String>? = null,
    val config: JsonNode? = null,
    val permissions: JsonNode? = null,
    val modelMaxBudget: JsonNode? = null,
    val budgetFallbacks: JsonNode? = null,
    val policies: List<String>? = null,
    val blocked: Boolean? = null,
    val aliases: JsonNode? = null,
    val accessGroupIds: List<String>? = null,
    val routerSettings: JsonNode? = null,
)

data class KeyUpdateRequest(
    val key: String? = null,
    val keyAlias: String? = null,
    val duration: String? = null,
    val spend: Double? = null,
    val models: List<String>? = null,
    val maxBudget: Double? = null,
    val userId: String? = null,
    val teamId: String? = null,
    val agentId: String? = null,
    val projectId: String? = null,
    val organizationId: String? = null,
    val maxParallelRequests: Int? = null,
    val metadata: JsonNode? = null,
    val tpmLimit: Long? = null,
    val rpmLimit: Long? = null,
    val tpdLimit: Long? = null,
    val budgetDuration: String? = null,
    val allowedCacheControls: List<String>? = null,
    val config: JsonNode? = null,
    val permissions: JsonNode? = null,
    val modelMaxBudget: JsonNode? = null,
    val budgetFallbacks: JsonNode? = null,
    val policies: List<String>? = null,
    val blocked: Boolean? = null,
    val aliases: JsonNode? = null,
    val accessGroupIds: List<String>? = null,
)

data class KeyDeleteRequest(val keys: List<String> = emptyList())

data class KeySingleRequest(val key: String? = null)

data class KeyListParams(
    val page: Int = 1,
    val size: Int = 10,
    val userId: String? = null,
    val teamId: String? = null,
    val organizationId: String? = null,
    val keyHash: String? = null,
    val keyAlias: String? = null,
    val search: String? = null,
    val returnFullObject: Boolean = false,
    val includeTeamKeys: Boolean = false,
    val includeCreatedByKeys: Boolean = false,
    val sortBy: String? = null,
    val sortOrder: String = "desc",
    val status: String? = null,
    val projectId: String? = null,
    val agentId: String? = null,
    val substringMatching: Boolean = false,
)

@Service
class KeyManagementService(
    private val tokens: VerificationTokenRepository,
    private val deletedTokens: DeletedTokenRepository,
) {

    fun generate(request: KeyGenerateRequest, principal: Principal): Map<String, Any?> {
        val rawKey = resolveRawKey(request.key)
        val now = Instant.now()
        val touched = touchedBy(principal)
        val entity = VerificationTokenEntity().apply {
            token = Hashing.sha256Hex(rawKey)
            keyName = Hashing.abbreviateApiKey(rawKey)
            keyAlias = request.keyAlias
            models = request.models ?: emptyList()
            maxBudget = request.maxBudget
            userId = request.userId
            teamId = request.teamId
            agentId = request.agentId
            projectId = request.projectId
            organizationId = request.organizationId
            keyType = request.keyType ?: "default"
            maxParallelRequests = request.maxParallelRequests
            tpmLimit = request.tpmLimit
            rpmLimit = request.rpmLimit
            tpdLimit = request.tpdLimit
            budgetDuration = request.budgetDuration
            allowedCacheControls = request.allowedCacheControls ?: emptyList()
            policies = request.policies ?: emptyList()
            blocked = request.blocked
            metadata = request.metadata ?: JsonNodeFactory.instance.objectNode()
            config = request.config ?: JsonNodeFactory.instance.objectNode()
            permissions = request.permissions ?: JsonNodeFactory.instance.objectNode()
            modelMaxBudget = request.modelMaxBudget ?: JsonNodeFactory.instance.objectNode()
            budgetFallbacks = request.budgetFallbacks ?: JsonNodeFactory.instance.objectNode()
            aliases = request.aliases ?: JsonNodeFactory.instance.objectNode()
            accessGroupIds = request.accessGroupIds ?: emptyList()
            routerSettings = request.routerSettings ?: JsonNodeFactory.instance.objectNode()
            allowedRoutes = emptyList()
            expires = request.duration?.let { now.plus(parseDuration(it)) }
            createdAt = now
            createdBy = touched
            updatedAt = now
            updatedBy = touched
            rotationCount = 0
            autoRotate = false
        }
        checkGeneratePermission(entity, principal)
        val saved = tokens.saveAndFlush(entity)
        return KeyViews.generateResponse(saved, rawKey, request.policies)
    }

    fun list(params: KeyListParams, principal: Principal): Map<String, Any?> {
        if (params.status == "deleted") {
            val rows = deletedTokens.findAll().filter { row ->
                (params.userId == null || row.userId == params.userId)
                    && (params.teamId == null || row.teamId == params.teamId)
                    && (params.keyHash == null || row.token == params.keyHash)
            }.sortedByDescending { it.deletedAt }
            return paginate(rows, params) { row ->
                if (params.returnFullObject) KeyViews.listView(viewRow(row)) else row.token
            }
        }
        val effective = if (principal.isProxyAdmin) params else params.copy(userId = principal.userId)
        val now = Instant.now()
        val rows = tokens.findAll().filter { row ->
            (effective.userId == null || matchesUserId(row.userId, effective.userId, effective.substringMatching, principal))
                && (effective.teamId == null || row.teamId == effective.teamId)
                && (effective.organizationId == null || row.organizationId == effective.organizationId)
                && (effective.keyHash == null || row.token == effective.keyHash)
                && (effective.keyAlias == null || matchesAlias(row.keyAlias, effective.keyAlias, effective.substringMatching))
                && (effective.projectId == null || row.projectId == effective.projectId)
                && (effective.agentId == null || row.agentId == effective.agentId)
                && (effective.search == null || row.token == effective.search
                    || (row.keyAlias?.contains(effective.search, ignoreCase = true) ?: false))
                && matchesStatus(row, effective.status, now)
        }
        return paginate(sortRows(rows, effective), effective) { row ->
            if (effective.returnFullObject) KeyViews.listView(row) else row.token
        }
    }

    fun info(key: String?, principal: Principal): Map<String, Any?> {
        val lookupKey = key ?: principal.rawKey
            ?: throw ProxyError("Key not found in database", "not_found_error", "key", 404)
        val hash = if (lookupKey.startsWith("sk-")) Hashing.sha256Hex(lookupKey) else lookupKey
        val live = tokens.findByToken(hash).orElse(null)
        if (live != null) {
            if (!principal.isProxyAdmin && live.userId != principal.userId && live.createdBy != principal.userId) {
                throw ProxyError.forbidden("You are not allowed to access this key's info. Your role=${principal.userRole ?: "None"}")
            }
            return linkedMapOf("key" to lookupKey, "info" to KeyViews.infoResponse(live, statusOf(live)))
        }
        val archived = deletedTokens.findByToken(hash)
            .orElseThrow { ProxyError("Key not found in database", "not_found_error", "key", 404) }
        return linkedMapOf("key" to lookupKey, "info" to KeyViews.deletedInfoView(archived, "deleted"))
    }

    fun update(request: KeyUpdateRequest, principal: Principal): Map<String, Any?> {
        val rawKey = requireKeyField(request.key)
        val hash = Hashing.sha256Hex(rawKey)
        val entity = tokens.findByToken(hash)
            .orElseThrow { ProxyError("Key not found.", "not_found_error", "key", 404) }
        checkKeyAccess(entity, principal, "not allowed to update this key. Your role=")
        val now = Instant.now()
        entity.apply {
            request.keyAlias?.let { keyAlias = it }
            request.models?.let { models = it }
            request.maxBudget?.let { maxBudget = it }
            request.userId?.let { userId = it }
            request.teamId?.takeIf { it.isNotBlank() }?.let { teamId = it }
            request.agentId?.let { agentId = it }
            request.projectId?.let { projectId = it }
            request.organizationId?.takeIf { it.isNotBlank() }?.let { organizationId = it }
            request.maxParallelRequests?.let { maxParallelRequests = it }
            request.metadata?.let { metadata = it }
            request.tpmLimit?.let { tpmLimit = it }
            request.rpmLimit?.let { rpmLimit = it }
            request.tpdLimit?.let { tpdLimit = it }
            request.budgetDuration?.let { budgetDuration = it }
            request.allowedCacheControls?.let { allowedCacheControls = it }
            request.config?.let { config = it }
            request.permissions?.let { permissions = it }
            request.modelMaxBudget?.let { modelMaxBudget = it }
            request.policies?.let { policies = it }
            request.blocked?.let { blocked = it }
            request.aliases?.let { aliases = it }
            request.accessGroupIds?.let { accessGroupIds = it }
            request.duration?.let { expires = now.plus(parseDuration(it)) }
            request.spend?.let { spend = it }
            settingsUpdatedAt = now
            updatedAt = now
            updatedBy = touchedBy(principal)
        }
        val saved = tokens.saveAndFlush(entity)
        return KeyViews.updateView(saved, rawKey)
    }

    fun block(request: KeySingleRequest, principal: Principal): Map<String, Any?> {
        val entity = findKey(request)
        checkKeyAccess(entity, principal, "not allowed to block this key. Your role=")
        val now = Instant.now()
        entity.blocked = true
        entity.settingsUpdatedAt = now
        entity.updatedAt = now
        entity.updatedBy = touchedBy(principal)
        return KeyViews.blockView(tokens.saveAndFlush(entity))
    }

    fun unblock(request: KeySingleRequest, principal: Principal): Map<String, Any?> {
        val entity = findKey(request)
        checkKeyAccess(entity, principal, "not allowed to unblock this key. Your role=")
        val now = Instant.now()
        entity.blocked = false
        entity.settingsUpdatedAt = now
        entity.updatedAt = now
        entity.updatedBy = touchedBy(principal)
        return KeyViews.unblockView(tokens.saveAndFlush(entity))
    }

    fun delete(request: KeyDeleteRequest, principal: Principal): Map<String, Any?> {
        val deleted = request.keys.mapNotNull { raw ->
            val hash = Hashing.sha256Hex(raw)
            val entity = tokens.findByToken(hash).orElse(null) ?: return@mapNotNull null
            checkKeyAccess(entity, principal, "not allowed to delete this key. Your role=")
            deletedTokens.save(deletedRecordOf(entity, principal))
            tokens.delete(entity)
            raw
        }
        return linkedMapOf("deleted_keys" to deleted)
    }

    private fun findKey(request: KeySingleRequest): VerificationTokenEntity {
        val raw = requireKeyField(request.key)
        val hash = if (raw.startsWith("sk-")) Hashing.sha256Hex(raw) else raw
        return tokens.findByToken(hash)
            .orElseThrow { ProxyError("Key not found.", "not_found_error", "key", 404) }
    }

    private fun requireKeyField(key: String?): String =
        key ?: throw DetailError(
            422,
            listOf(mapOf("type" to "missing", "loc" to listOf("body", "key"), "msg" to "Field required")),
        )

    private fun resolveRawKey(requested: String?): String {
        if (requested == null) return "sk-" + Hashing.randomUrlSafeToken(16)
        if (!requested.startsWith("sk-")) {
            val masked =
                if (requested.length > 8) requested.substring(0, 4) + "****" + requested.substring(requested.length - 4)
                else "****"
            throw ProxyError.badRequest(
                mapOf("error" to "Invalid key format. LiteLLM Virtual Key must start with 'sk-'. Received: $masked"),
            )
        }
        if (requested.length < MINIMUM_CUSTOM_KEY_LENGTH) {
            throw ProxyError.badRequest(
                mapOf(
                    "error" to "Invalid key format. LiteLLM Virtual Key must be at least $MINIMUM_CUSTOM_KEY_LENGTH characters long."
                ),
            )
        }
        return requested
    }

    private fun checkGeneratePermission(entity: VerificationTokenEntity, principal: Principal) {
        if (principal.isProxyAdmin) return
        if (entity.userId != null && entity.userId != principal.userId) {
            throw ProxyError.forbidden("You do not have permission to access this resource.")
        }
        if (entity.teamId != null) {
            throw ProxyError.forbidden("You do not have permission to access this resource.")
        }
    }

    private fun checkKeyAccess(entity: VerificationTokenEntity, principal: Principal, forbiddenSuffix: String) {
        if (principal.isProxyAdmin) return
        val self = principal.userId
        if (entity.userId != self && entity.createdBy != self) {
            throw ProxyError.forbidden("You are $forbiddenSuffix${principal.userRole ?: "None"}")
        }
    }

    private fun matchesUserId(value: String?, expected: String?, substring: Boolean, principal: Principal): Boolean {
        if (value == null) return false
        if (substring && principal.isProxyAdmin && expected != null) return value.contains(expected, ignoreCase = true)
        return value == expected
    }

    private fun matchesAlias(value: String?, expected: String?, substring: Boolean): Boolean {
        if (value == null || expected == null) return false
        return if (substring) value.contains(expected, ignoreCase = true) else value == expected
    }

    private fun matchesStatus(row: VerificationTokenEntity, status: String?, now: Instant): Boolean {
        if (status == null) return true
        val blocked = row.blocked == true
        val expires = row.expires
        val expired = expires != null && expires < now
        return when (status) {
            "active" -> !blocked && !expired
            "expired" -> !blocked && expired
            "revoked" -> blocked
            else -> true
        }
    }

    private fun statusOf(row: VerificationTokenEntity): String {
        if (row.blocked == true) return "revoked"
        val expires = row.expires
        if (expires != null && expires < Instant.now()) return "expired"
        return "active"
    }

    private fun sortRows(rows: List<VerificationTokenEntity>, params: KeyListParams): List<VerificationTokenEntity> {
        val ascending = params.sortOrder.equals("asc", ignoreCase = true)
        val comparator: Comparator<VerificationTokenEntity> = when (params.sortBy) {
            "spend" -> compareBy { it.spend }
            "user_id" -> compareBy { it.userId ?: "" }
            "key_alias" -> compareBy { it.keyAlias ?: "" }
            "max_budget" -> compareBy { it.maxBudget ?: 0.0 }
            else -> compareBy { it.createdAt }
        }
        val result = rows.sortedWith(comparator)
        return if (ascending) result else result.reversed()
    }

    private fun <T> paginate(rows: List<T>, params: KeyListParams, mapper: (T) -> Any?): Map<String, Any?> {
        val start = (params.page - 1) * params.size
        val slice = rows.drop(start).take(params.size)
        return linkedMapOf(
            "keys" to slice.map(mapper),
            "total_count" to rows.size,
            "current_page" to params.page,
            "total_pages" to ((rows.size + params.size - 1) / params.size).coerceAtLeast(1),
        )
    }

    private fun viewRow(row: ai.litellm.backend.domain.DeletedTokenEntity): VerificationTokenEntity =
        VerificationTokenEntity().apply {
            token = row.token
            keyName = row.keyName
            keyAlias = row.keyAlias
            softBudgetCooldown = row.softBudgetCooldown
            spend = row.spend
            totalSpend = row.totalSpend
            expires = row.expires
            models = row.models
            userId = row.userId
            teamId = row.teamId
            agentId = row.agentId
            projectId = row.projectId
            maxParallelRequests = row.maxParallelRequests
            blocked = row.blocked
            tpmLimit = row.tpmLimit
            rpmLimit = row.rpmLimit
            tpdLimit = row.tpdLimit
            maxBudget = row.maxBudget
            budgetDuration = row.budgetDuration
            budgetResetAt = row.budgetResetAt
            allowedCacheControls = row.allowedCacheControls
            allowedRoutes = row.allowedRoutes
            keyType = row.keyType
            policies = row.policies
            accessGroupIds = row.accessGroupIds
            budgetId = row.budgetId
            organizationId = row.organizationId
            objectPermissionId = row.objectPermissionId
            createdAt = row.deletedAt ?: row.createdAt
            createdBy = row.deletedBy ?: row.createdBy
            updatedAt = row.updatedAt
            updatedBy = row.updatedBy
            rotationCount = row.rotationCount ?: 0
            autoRotate = row.autoRotate ?: false
            rotationInterval = row.rotationInterval
            lastRotationAt = row.lastRotationAt
            keyRotationAt = row.keyRotationAt
            lastActive = row.lastActive
            settingsUpdatedAt = row.settingsUpdatedAt
        }

    private fun parseDuration(text: String): Duration {
        val match = Regex("^(\\d+)(s|m|h|d|mo|y)$").matchEntire(text.trim())
            ?: throw ProxyError.badRequest(mapOf("error" to "Invalid duration format: $text"))
        val (amount, unit) = match.destructured
        val n = amount.toLong()
        return when (unit) {
            "s" -> Duration.ofSeconds(n)
            "m" -> Duration.ofMinutes(n)
            "h" -> Duration.ofHours(n)
            "d" -> Duration.ofDays(n)
            "mo" -> Duration.ofDays(n * 30)
            "y" -> Duration.ofDays(n * 365)
            else -> throw DetailError(400, mapOf("error" to "Invalid duration format: $text"))
        }
    }

    companion object {
        const val MINIMUM_CUSTOM_KEY_LENGTH = 16
    }
}
