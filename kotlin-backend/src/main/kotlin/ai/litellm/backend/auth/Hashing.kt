package ai.litellm.backend.auth

import org.bouncycastle.crypto.generators.SCrypt
import java.security.MessageDigest
import java.security.SecureRandom
import java.util.Arrays
import java.util.Base64

object Hashing {
    private val secureRandom = SecureRandom()

    fun sha256Hex(value: String): String {
        val digest = MessageDigest.getInstance("SHA-256").digest(value.toByteArray(Charsets.UTF_8))
        return digest.joinToString("") { "%02x".format(it) }
    }

    fun scrypt(password: String, salt: ByteArray, n: Int = 16384, r: Int = 8, p: Int = 1, dkLen: Int = 32): ByteArray =
        SCrypt.generate(password.toByteArray(Charsets.UTF_8), salt, n, r, p, dkLen)

    fun hashPassword(password: String): String {
        val salt = ByteArray(16).also { secureRandom.nextBytes(it) }
        val dk = scrypt(password, salt)
        return "scrypt:" + Base64.getEncoder().encodeToString(salt + dk)
    }

    fun verifyPassword(password: String, stored: String): Boolean {
        return if (stored.startsWith("scrypt:")) {
            try {
                val raw = Base64.getDecoder().decode(stored.removePrefix("scrypt:"))
                val salt = raw.copyOfRange(0, 16)
                val expected = raw.copyOfRange(16, 48)
                val actual = scrypt(password, salt)
                Arrays.equals(expected, actual)
            } catch (e: Exception) {
                false
            }
        } else {
            sha256Hex(password) == stored
        }
    }

    fun randomUrlSafeToken(lengthBytes: Int): String {
        val bytes = ByteArray(lengthBytes).also { secureRandom.nextBytes(it) }
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes)
    }

    fun abbreviateApiKey(apiKey: String): String {
        if (apiKey.length < 16) return "sk-..."
        return "sk-..." + apiKey.substring(apiKey.length - 4)
    }
}
