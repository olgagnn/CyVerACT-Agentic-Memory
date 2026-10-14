from Agent_Memory.memory_driver import get_memory_driver
# Initializing memory with the rules

ERROR_FIX_RULES = [
    {
        "name": "ExecutionFailed",
        "category": "SyntaxValidator",
        "rule": (
            "Generate only structurally sound queries that can be successfully parsed "
            "and executed by the database engine without failing at runtime."
        ),
    },
    {
        "name": "SyntaxError",
        "category": "SyntaxValidator",
        "rule": (
            "Strictly adhere to valid query syntax (e.g., standard Cypher). "
            "Do not hallucinate unsupported clauses, keywords, or invalid operators."
        ),
    },
    {
        "name": "ParameterNotProvided",
        "category": "SyntaxValidator",
        "rule": (
            "If utilizing parameterized variables in the query (e.g., $param), verify that "
            "you are not referencing parameters that have not been explicitly defined or "
            "passed to the environment."
        ),
    },
    {
        "name": "UnsatisfiableRelationshipTypeExpression",
        "category": "SyntaxValidator",
        "rule": (
            "Construct logical relationship patterns. Avoid creating impossible, contradictory, "
            "or mutually exclusive relationship type constraints within a single match clause."
        ),
    },
    {
        "name": "ProcedureNotFound",
        "category": "SyntaxValidator",
        "rule": (
            "Only invoke built-in database functions or verified, standard plugin procedures. "
            "Do not guess or invent procedure names."
        ),
    },
    {
        "name": "ArithmeticError",
        "category": "SyntaxValidator",
        "rule": (
            "Implement mathematical safety checks within the query; ensure that dynamic or "
            "static divisors cannot evaluate to zero to prevent division-by-zero runtime errors."
        ),
    },
    {
        "name": "ConflictingVariablesError",
        "category": "SyntaxValidator",
        "rule": (
            "Maintain strict variable scope and typing. Never assign conflicting node labels "
            "or relationship types to the same variable name within the same query."
        ),
    },
    {
        "name": "UnknownLabelWarning",
        "category": "SchemaValidator",
        "rule": (
            "Only utilize node labels that are explicitly confirmed to exist within the "
            "provided knowledge graph schema."
        ),
    },
    {
        "name": "UnknownRelationshipTypeWarning",
        "category": "SchemaValidator",
        "rule": (
            "Ensure all relationship types exactly match the defined relationships in the "
            "database schema. Do not guess relationship names."
        ),
    },
    {
        "name": "UnknownPathWarning",
        "category": "SchemaValidator",
        "rule": (
            "Validate that the structural combination of nodes and relationships forming a path "
            "actually exists in the schema's topological layout before querying it."
        ),
    },
    {
        "name": "WrongDirectionPathWarning",
        "category": "SchemaValidator",
        "rule": (
            "Pay strict attention to relationship directionality (e.g., (a)-[:REL]->(b) vs. "
            "(a)<-[:REL]-(b)). Ensure the query aligns perfectly with the directed nature of the graph."
        ),
    },
    {
        "name": "VariableLengthPathWarning",
        "category": "SchemaValidator",
        "rule": (
            "When querying paths of unknown depth, use the unbounded wildcard operator (*) safely, "
            "rather than assuming specific fixed bounds (like *X..Y), unless exact depth bounds are "
            "strictly verified by the schema."
        ),
    },
    {
        "name": "WrongDirectionPath&VariableLengthPathWarning",
        "category": "SchemaValidator",
        "rule": (
            "Double-check both the directionality arrows and the variable-length traversal syntax "
            "simultaneously to ensure the multi-hop path accurately reflects how the relationships "
            "traverse the graph."
        ),
    },
    {
        "name": "UnknownPropertyKeyWarning",
        "category": "PropertiesValidator",
        "rule": (
            "Only query or filter by property keys that are explicitly defined in the schema dictionary."
        ),
    },
    {
        "name": "InvalidPropertyAccessByLabelWarning",
        "category": "PropertiesValidator",
        "rule": (
            "Cross-reference property keys with their correct node labels or relationship types. "
            "Never attempt to access or return a property from an entity that does not inherently support it."
        ),
    },
]


UPSERT_ERROR_TYPE_AND_RULE = """
MERGE (et:ErrorType {name: $name})
SET et.category = $category
MERGE (fr:FixRule {rule: $rule})
MERGE (et)-[:FIXED_WITH]->(fr)
"""

VALIDATE_RULES = """
UNWIND $names AS expected_name
OPTIONAL MATCH (et:ErrorType {name: expected_name})
OPTIONAL MATCH (et)-[:FIXED_WITH]->(fr:FixRule)
RETURN expected_name,
       et.category AS category,
       collect(DISTINCT fr.rule) AS rules
ORDER BY expected_name
"""

LEGACY_ERROR_TYPE_NAME = "WrongDirectionPathAndVariableLengthWarning"


def initialize_memory_graph(driver) -> None:
    """Create or update the predefined ErrorType -> FixRule knowledge."""
    with driver.session() as session:
        for item in ERROR_FIX_RULES:
            session.run(
                UPSERT_ERROR_TYPE_AND_RULE,
                name=item["name"],
                category=item["category"],
                rule=item["rule"],
            ).consume()


def validate_memory_graph(driver) -> None:
    """Verify that every expected ErrorType has the expected category and FixRule."""
    expected = {item["name"]: item for item in ERROR_FIX_RULES}

    with driver.session() as session:
        records = session.run(
            VALIDATE_RULES,
            names=list(expected.keys()),
        )

        problems = []
        for record in records:
            name = record["expected_name"]
            category = record["category"]
            rules = record["rules"]
            expected_item = expected[name]

            if category != expected_item["category"]:
                problems.append(
                    f"{name}: expected category {expected_item['category']!r}, got {category!r}"
                )

            if rules != [expected_item["rule"]]:
                problems.append(
                    f"{name}: expected exactly one matching FixRule, got {len(rules)}"
                )

        legacy_count = session.run(
            "MATCH (et:ErrorType {name: $name}) RETURN count(et) AS count",
            name=LEGACY_ERROR_TYPE_NAME,
        ).single()["count"]

    if problems:
        print("\nMemory graph initialization completed, but validation found problems:")
        for problem in problems:
            print(f"  - {problem}")
        raise RuntimeError("Memory graph validation failed.")

    print(f"\nValidated {len(ERROR_FIX_RULES)} ErrorType/FixRule mappings successfully.")

    if legacy_count:
        print(
            "\nWARNING: A legacy ErrorType named "
            f"'{LEGACY_ERROR_TYPE_NAME}' still exists in this database. "
            "The final implementation uses "
            "'WrongDirectionPath&VariableLengthPathWarning'. "
            "It is safe to leave the legacy node untouched for historical experiment data, "
            "or remove it separately after confirming it is no longer needed."
        )


def main() -> None:
    driver = get_memory_driver()
    try:
        driver.verify_connectivity()
        print("Connected to the Neo4j memory database.")
        initialize_memory_graph(driver)
        validate_memory_graph(driver)
        print("Memory graph initialization completed successfully.")
    finally:
        driver.close()


if __name__ == "__main__":
    main()