from neo4j import GraphDatabase
import os 
from Agent_Memory.custom_cyver_memory import CyVerMemory

# Init Custom Memory
URI = os.getenv("NEO4J_URI")
USER = os.getenv("NEO4J_USERNAME")
PASSWORD = os.getenv("NEO4J_PASSWORD")
DB_NAME = os.getenv("MEMORY_DATABASE")

def initialize_database():
    driver = GraphDatabase.driver(
        URI,
        auth=(USER, PASSWORD)
    )

    cypher_constraints = """
    CREATE CONSTRAINT session_id IF NOT EXISTS
    FOR (s:Session)
    REQUIRE s.session_id IS UNIQUE;
    """

    cypher_vector = """
    CREATE VECTOR INDEX rule_embedding IF NOT EXISTS
    FOR (r:FixRule) ON (r.embedding)
    OPTIONS {
        indexConfig: {
            `vector.dimensions`: 384,
            `vector.similarity_function`: 'cosine'
        }
    };
    """

    # Specify database here
    with driver.session(database=DB_NAME) as session:
        session.run(cypher_constraints)
        session.run(cypher_vector)
        print(f"CyVerAct Memory Schema successfully initialized in DB: {DB_NAME}")

    driver.close()