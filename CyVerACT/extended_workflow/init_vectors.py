import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv(override=True)

URI = os.getenv("NEO4J_URI")
AUTH = (
    os.getenv("NEO4J_USERNAME"),
    os.getenv("NEO4J_PASSWORD")
)

driver = GraphDatabase.driver(URI, auth=AUTH)

with driver.session() as session:
    # --- INDEX 1: EPISODIC QUESTION EMBEDDINGS (Pre-generation) ---
    print("Creating Question Vector Index...")
    session.run("""
    CREATE VECTOR INDEX question_embeddings IF NOT EXISTS
    FOR (q:Question) ON (q.embedding)
    OPTIONS {indexConfig: {
      `vector.dimensions`: 384,
      `vector.similarity_function`: 'cosine'
    }}
    """)

    # --- INDEX 2: CYPHER ERROR SEMANTICS (The specific database failure) --- 
    print("Creating Error Vector Index...")
    session.run("""
    CREATE VECTOR INDEX error_vector_embeddings IF NOT EXISTS
    FOR (e:CypherError) ON (e.error_embedding)
    OPTIONS {indexConfig: {
      `vector.dimensions`: 384,
      `vector.similarity_function`: 'cosine'
    }}
    """)

    # --- INDEX 3: TRAJECTORY SEMANTICS (The structural intent) --- 
    print("Creating Trajectory Vector Index...")
    session.run("""
    CREATE VECTOR INDEX trajectory_vector_embeddings IF NOT EXISTS
    FOR (e:CypherError) ON (e.trajectory_embedding)
    OPTIONS {indexConfig: {
      `vector.dimensions`: 384,
      `vector.similarity_function`: 'cosine'
    }}
    """)

print("\nDatabase vector indexes successfully configured.")
driver.close()