from operator import add
from typing import Annotated, List
from typing_extensions import TypedDict

class InputState(TypedDict):
    question: str
    # schema: str
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
    cypher_statement: str
    database_records: List[dict]
    path: Annotated[List[str], add]
    total_tokens: Annotated[List[int], add]
    completion_tokens: Annotated[List[int], add]
    prompt_tokens: Annotated[List[int], add]


class OutputState(TypedDict):
    path: List[str]
    cypher_statement: str
    database_records: List[dict]
    total_tokens: List[int]
    completion_tokens: List[int]
    prompt_tokens: List[int]