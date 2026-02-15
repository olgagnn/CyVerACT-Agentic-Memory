from neo4j import GraphDatabase, basic_auth
from Nodes.States.states import OverallState

# no_results = "I couldn't find any relevant information in the database"

def cypher_executor(state: OverallState) -> OverallState:
    """
    Executes the given Cypher statement over the knowledge graph.
    """
    print('Cypher Executor: START')

    cypher_statement = state.get("cypher_statement")
    database_url = state.get("database_url")
    database_name = state.get("database_name")
    database_user = state.get("database_user")
    database_password = state.get("database_password")

    database_records = []

    # Checking for Cypher Query
    if not cypher_statement:
        print("No Cypher statement found.")
        return {
            "database_records": [],
            "next_action": "output_generator",
            "path": ["cypher_executor"]
        }

    driver = None
    try:
        # Driver connection 
        if database_url and database_user and database_password:
            driver = GraphDatabase.driver(database_url, auth=(database_user, database_password))
            
            # Execute Query
            result = driver.execute_query(cypher_statement, database_=database_name)
            
            # Results formatting in dictionaries
            for record in result.records:
                database_records.append(record.data())
            
            print(f"Executing Cypher: {cypher_statement}")
            print(f"Records found: {len(database_records)}")
        else:
            print("ERROR: Database credentials missing in State inputs.")
            
    except Exception as e:
        print(f"Error executing Cypher: {e}")
        database_records = []
        
    finally:
        # Ending connection
        if driver:
            driver.close()

    print('Cypher Executor: END')

    #Connect to the database
    # driver = state.get("neo4j_driver")
    # driver = GraphDatabase.driver(database_url, auth=basic_auth(database_user, database_password) )
    # print('Cypher Executor: START')
    # database_records = None
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
    
    return {
        "database_records": database_records,
        "next_action": "output_generator",
        "path": ["cypher_executor"],
        "total_tokens": [-1],
        "prompt_tokens": [-1],
        "completion_tokens": [-1]
    }