package ai.litellm.backend.auth

import ai.litellm.backend.domain.DeletedTokenEntity
import ai.litellm.backend.domain.VerificationTokenEntity
import java.time.Instant

fun deletedRecordOf(row: VerificationTokenEntity, principal: Principal): DeletedTokenEntity =
    DeletedTokenEntity().apply {
        token = row.token
        keyName = row.keyName
        keyAlias = row.keyAlias
        softBudgetCooldown = row.softBudgetCooldown
        spend = row.spend
        totalSpend = row.totalSpend
        expires = row.expires
        models = row.models
        aliases = row.aliases
        config = row.config
        userId = row.userId
        teamId = row.teamId
        agentId = row.agentId
        projectId = row.projectId
        permissions = row.permissions
        maxParallelRequests = row.maxParallelRequests
        metadata = row.metadata
        blocked = row.blocked
        tpmLimit = row.tpmLimit
        rpmLimit = row.rpmLimit
        tpdLimit = row.tpdLimit
        maxBudget = row.maxBudget
        budgetDuration = row.budgetDuration
        budgetResetAt = row.budgetResetAt
        allowedCacheControls = row.allowedCacheControls
        allowedRoutes = row.allowedRoutes
        policies = row.policies
        accessGroupIds = row.accessGroupIds
        keyType = row.keyType
        modelSpend = row.modelSpend
        modelMaxBudget = row.modelMaxBudget
        budgetFallbacks = row.budgetFallbacks
        routerSettings = row.routerSettings
        budgetId = row.budgetId
        organizationId = row.organizationId
        objectPermissionId = row.objectPermissionId
        createdAt = row.createdAt
        createdBy = row.createdBy
        updatedAt = row.updatedAt
        updatedBy = row.updatedBy
        rotationCount = row.rotationCount
        autoRotate = row.autoRotate
        rotationInterval = row.rotationInterval
        lastRotationAt = row.lastRotationAt
        keyRotationAt = row.keyRotationAt
        lastActive = row.lastActive
        settingsUpdatedAt = row.settingsUpdatedAt
        deletedAt = Instant.now()
        deletedBy = principal.userId
        deletedByApiKey =
            if (principal.source == AuthSource.MASTER_KEY) "litellm_proxy_master_key" else principal.rawKey
    }
