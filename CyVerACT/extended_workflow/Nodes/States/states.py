from operator import add
from typing import Annotated, List,Any
from neo4j import GraphDatabase, Driver
from typing_extensions import TypedDict

class InputState(TypedDict):
    question: str
    # schema: str
    # loop_count: int
    database_url :str
    database_name: str
    database_user: str
    database_password: str


class OverallState(TypedDict):
    question: str
    schema: str
    # filtered_schema:str
    database_url :str
    database_name: str
    database_user: str
    database_password: str
    neo4j_driver: Driver
    next_action: str
    cypher_statement: str
    correct_output: bool
    cypher_errors: List[str]
    internal_cypher_errors_history: Annotated[List[Any], add]
    database_records: List[dict]
    path: Annotated[List[str], add]
    total_tokens: Annotated[List[int], add]
    completion_tokens: Annotated[List[int], add]
    prompt_tokens: Annotated[List[int], add]

class OutputState(TypedDict):
    answer: str
    path: List[str]
    is_KG_Valid_correct: bool
    cypher_statement: str
    database_records: List[dict]
    cypher_errors: List[str]
    cypher_errors_history: Annotated[List[Any], add]
    total_tokens: List[int]
    completion_tokens: List[int]
    prompt_tokens: List[int]

# class UnavailableOutputState(TypedDict):
#     # answer: str
#     correct_output: bool
#     path: List[str]