from typing import List, Optional
from cognee.low_level import DataPoint


# Error Type
class CypherErrorType(DataPoint):
    """
    High-level category of Cypher errors
    (e.g., SyntaxError, AggregationError, DirectionError, SchemaError)
    """
    name: str


# Cypher Error
class CypherError(DataPoint):
    """
    Specific Cypher error instance
    """
    name: str
    description: Optional[str] = None
    is_type: Optional[CypherErrorType] = None


# Fix Rule
class FixRule(DataPoint):
    """
    General reusable rule to fix a type of Cypher error
    """
    description: str
    fixes: Optional[CypherError] = None


# Query Example
class QueryExample(DataPoint):
    """
    Concrete example of a failed query
    """
    user_query: str
    bad_cypher: str
    error_message: str
    related_error: Optional[CypherError] = None


# ROOT GRAPH MODEL
class CypherKnowledgeGraph(DataPoint):
    """
    Root model required by Cognee.
    This connects all entities into one graph.
    """
    errors: Optional[List[CypherError]] = None
    rules: Optional[List[FixRule]] = None
    examples: Optional[List[QueryExample]] = None