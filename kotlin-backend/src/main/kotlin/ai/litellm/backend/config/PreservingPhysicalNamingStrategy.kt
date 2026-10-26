package ai.litellm.backend.config

import org.hibernate.boot.model.naming.Identifier
import org.hibernate.boot.model.naming.PhysicalNamingStrategy
import org.hibernate.engine.jdbc.env.spi.JdbcEnvironment

class PreservingPhysicalNamingStrategy : PhysicalNamingStrategy {
    override fun toPhysicalCatalogName(name: Identifier?, jdbcEnvironment: JdbcEnvironment?): Identifier? = name

    override fun toPhysicalSchemaName(name: Identifier?, jdbcEnvironment: JdbcEnvironment?): Identifier? = name

    override fun toPhysicalTableName(name: Identifier?, jdbcEnvironment: JdbcEnvironment?): Identifier? = name

    override fun toPhysicalSequenceName(name: Identifier?, jdbcEnvironment: JdbcEnvironment?): Identifier? = name

    override fun toPhysicalColumnName(name: Identifier, jdbcEnvironment: JdbcEnvironment?): Identifier =
        Identifier.toIdentifier(camelToSnake(name.text))

    private fun camelToSnake(input: String): String {
        val result = StringBuilder(input.length + 4)
        input.forEachIndexed { index, char ->
            if (char.isUpperCase()) {
                if (index > 0) result.append('_')
                result.append(char.lowercaseChar())
            } else {
                result.append(char)
            }
        }
        return result.toString()
    }
}
