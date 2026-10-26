package ai.litellm.backend.controller

import ai.litellm.backend.auth.requirePrincipal
import ai.litellm.backend.service.KeyDeleteRequest
import ai.litellm.backend.service.KeyGenerateRequest
import ai.litellm.backend.service.KeyListParams
import ai.litellm.backend.service.KeyManagementService
import ai.litellm.backend.service.KeySingleRequest
import ai.litellm.backend.service.KeyUpdateRequest
import jakarta.servlet.http.HttpServletRequest
import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RequestParam
import org.springframework.web.bind.annotation.RestController

@RestController
class KeyController(private val keys: KeyManagementService) {

    @PostMapping("/key/generate")
    fun generate(@RequestBody request: KeyGenerateRequest, header: HttpServletRequest): Map<String, Any?> =
        keys.generate(request, requirePrincipal(header))

    @GetMapping("/key/list")
    fun list(
        @RequestParam(required = false, defaultValue = "1") page: Int,
        @RequestParam(required = false, defaultValue = "10") size: Int,
        @RequestParam(required = false) user_id: String?,
        @RequestParam(required = false) team_id: String?,
        @RequestParam(required = false) organization_id: String?,
        @RequestParam(required = false) key_hash: String?,
        @RequestParam(required = false) key_alias: String?,
        @RequestParam(required = false) search: String?,
        @RequestParam(required = false, defaultValue = "false") return_full_object: Boolean,
        @RequestParam(required = false, defaultValue = "false") include_team_keys: Boolean,
        @RequestParam(required = false, defaultValue = "false") include_created_by_keys: Boolean,
        @RequestParam(required = false) sort_by: String?,
        @RequestParam(required = false, defaultValue = "desc") sort_order: String,
        @RequestParam(required = false) status: String?,
        @RequestParam(required = false) project_id: String?,
        @RequestParam(required = false) agent_id: String?,
        @RequestParam(required = false, defaultValue = "false") substring_matching: Boolean,
        header: HttpServletRequest,
    ): Map<String, Any?> =
        keys.list(
            KeyListParams(
                page = page,
                size = size,
                userId = user_id,
                teamId = team_id,
                organizationId = organization_id,
                keyHash = key_hash,
                keyAlias = key_alias,
                search = search,
                returnFullObject = return_full_object,
                includeTeamKeys = include_team_keys,
                includeCreatedByKeys = include_created_by_keys,
                sortBy = sort_by,
                sortOrder = sort_order,
                status = status,
                projectId = project_id,
                agentId = agent_id,
                substringMatching = substring_matching,
            ),
            requirePrincipal(header),
        )

    @GetMapping("/key/info")
    fun info(
        @RequestParam(required = false) key: String?,
        header: HttpServletRequest,
    ): Map<String, Any?> = keys.info(key, requirePrincipal(header))

    @PostMapping("/key/update")
    fun update(@RequestBody request: KeyUpdateRequest, header: HttpServletRequest): Map<String, Any?> =
        keys.update(request, requirePrincipal(header))

    @PostMapping("/key/block")
    fun block(@RequestBody request: KeySingleRequest, header: HttpServletRequest): Map<String, Any?> =
        keys.block(request, requirePrincipal(header))

    @PostMapping("/key/unblock")
    fun unblock(@RequestBody request: KeySingleRequest, header: HttpServletRequest): Map<String, Any?> =
        keys.unblock(request, requirePrincipal(header))

    @PostMapping("/key/delete")
    fun delete(@RequestBody request: KeyDeleteRequest, header: HttpServletRequest): Map<String, Any?> =
        keys.delete(request, requirePrincipal(header))
}
