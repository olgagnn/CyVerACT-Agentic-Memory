from langchain_huggingface import HuggingFaceEmbeddings
from neo4j import GraphDatabase

# Init local embedding model (384 dimensions)
embedder = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# Connect to db
URI = "bolt://localhost:7687" 
AUTH = ("neo4j", "agentmemory")
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

print("\nDatabase indexes successfully configured for Split Embeddings!")
driver.close()