from neo4j import GraphDatabase,basic_auth

from Nodes.States.states import  OverallState
from langchain_neo4j import Neo4jGraph



# no_results = "I couldn't find any relevant information in the database"


def cypher_executor(state: OverallState) -> OverallState:
    """
    Executes the given Cypher statement over the knowledge graph.
    """
    cypher_statement = state.get("cypher_statement")
    database_url = state.get("database_url")
    database_name = state.get("database_name")
    database_user = state.get("database_user")
    database_password = state.get("database_password")

    
    #Connect to the database
    enhanced_graph = Neo4jGraph(url=database_url, username = database_user,
                                password =  database_password, database = database_name,
                                enhanced_schema=True)


    print('-----------------------------------------------Cypher Executor: START')
    database_records = None
    try:
        records = enhanced_graph.query(cypher_statement)
        database_records = [record for record in records]
    except Exception as e:
            #could not be executed (e.g. implicit division by zero due to data availability)
            database_records = None

    # if cypher_statement == 'MATCH (u:User)-[:RATED]->(m:Movie)<-[:RATED]-(v:User) WHERE u.userId <> v.userId RETURN u.name, v.name':
    #     database_records = None
    # else:
    #     try:
    #         records = driver.execute_query(cypher_statement, database_= database_name)
    #         database_records = [record for record in records]
    #     except Exception as e:
    #         #could not be executed (e.g. implicit division by zero due to data availability)
    #         database_records = None

        # print('Records:\n', records)
        # print('Cypher Executor: END')
        # print()
    print('-----------------------------------------------Cypher Executor: END')
    
    return {
        "database_records": database_records,
        "next_action": "output_generator",
        "path": ["cypher_executor"],
        "total_tokens": [-1],
        "prompt_tokens": [-1],
        "completion_tokens": [-1]
    }