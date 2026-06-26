from neo4j import GraphDatabase,basic_auth

from Nodes.States.states import  OverallState,OutputState
from CyVer import SyntaxValidator

def cypher_executor(state: OverallState) -> OutputState:
    """
    Executes the given Cypher statement over the knowledge graph.
    """
    cypher_statement = state.get("cypher_statement")
    database_url = state.get("database_url")
    database_name = state.get("database_name")
    database_user = state.get("database_user")
    database_password = state.get("database_password")
    database_records= None

    #  #Connect to the database
    # driver = GraphDatabase.driver(database_url, auth=basic_auth(database_user, database_password) )
    # syntax_validator = SyntaxValidator(driver)
    # syntax_correct, _ = syntax_validator.validate(cypher_statement, database_name=database_name)
    # if syntax_correct:
    #     try:
    #         records = driver.execute_query(cypher_statement, database_= database_name)
    #         database_records = [record for record in records]
    #     except Exception as e:
    #     #could not be executed (e.g. implicit division by zero due to data availability)
    #         database_records = None
    # else:
    #     database_records= None
    # print('Records:\n', records)
    # print('---------------------------------')
    # output = [] #enhanced_graph.query(state.get("cypher_statement"))
    return {
        "path": ["cypher_executor"],
        "cypher_statement": state.get("cypher_statement"),
        "database_records": database_records,
        "total_tokens": [-1],
        "prompt_tokens": [-1],
        "completion_tokens": [-1]
    }