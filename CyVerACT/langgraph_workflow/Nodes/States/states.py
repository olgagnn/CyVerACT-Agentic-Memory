from operator import add
from typing import Annotated, List
from neo4j import GraphDatabase, Driver

from typing_extensions import TypedDict


class InputState(TypedDict):
    question: str
    database_url :str
    database_name: str
    database_user: str
    database_password: str


class OverallState(TypedDict):
    question: str
    database_url :str
    database_name: str
    database_user: str
    database_password: str
    neo4j_driver: Driver
    next_action: str
    cypher_statement: str
    cypher_errors: List[str]
    database_records: List[dict]
    path: Annotated[List[str], add]
    schema: str
    total_tokens: Annotated[List[int], add]
    completion_tokens: Annotated[List[int], add]
    prompt_tokens: Annotated[List[int], add]



class OutputState(TypedDict):
    answer: str
    path: List[str]
    cypher_statement: str
    database_records:List[dict]
    total_tokens: Annotated[List[int], add]
    completion_tokens: Annotated[List[int], add]
    prompt_tokens: Annotated[List[int], add]