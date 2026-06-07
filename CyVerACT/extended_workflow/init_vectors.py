from langchain_huggingface import HuggingFaceEmbeddings
from neo4j import GraphDatabase

# Init local embedding model (384 dimensions)
embedder = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# Connect to db
URI = "bolt://localhost:7687" 
AUTH = ("neo4j", "agentmemory")
driver = GraphDatabase.driver(URI, auth=AUTH)

with driver.session() as session:
    # --- INDEX 1: ERROR TYPE EMBEDDINGS ---
    print("Creating Error Type Vector Index...")
    session.run("""
    CREATE VECTOR INDEX error_embeddings IF NOT EXISTS
    FOR (et:ErrorType) ON (et.embedding)
    OPTIONS {indexConfig: {
      `vector.dimensions`: 384,
      `vector.similarity_function`: 'cosine'
    }}
    """)

    # --- INDEX 2: EPISODIC QUESTION EMBEDDINGS ---
    print("Creating Question Vector Index...")
    session.run("""
    CREATE VECTOR INDEX question_embeddings IF NOT EXISTS
    FOR (q:Question) ON (q.embedding)
    OPTIONS {indexConfig: {
      `vector.dimensions`: 384,
      `vector.similarity_function`: 'cosine'
    }}
    """)

    # --- INDEX 3: RAW CYPHER ERROR EMBEDDINGS --- 
    print("Creating CypherError Vector Index...")
    session.run("""
    CREATE VECTOR INDEX cypher_error_embeddings IF NOT EXISTS
    FOR (e:CypherError) ON (e.embedding)
    OPTIONS {
      indexConfig: {
        `vector.dimensions`: 384,
        `vector.similarity_function`: 'cosine'
    }}
    """)

    # --- INDEX 4: BM25 FULL-TEXT INDEX (FOR WRRF) ---
    print("Creating Full-Text Index for Keyword Search...")
    session.run("""
    CREATE FULLTEXT INDEX fixrule_text IF NOT EXISTS FOR (n:FixRule) ON EACH [n.rule]
    """)

    # --- POPULATING ERROR TYPE EMBEDDINGS ---
    print("Fetching existing ErrorTypes and their FixRules...")
    
    # We MATCH the ErrorType AND its connected FixRule to get a rich vocabulary string
    error_types = session.run("""
    MATCH (et:ErrorType)-[:FIXED_WITH]->(fr:FixRule) 
    RETURN elementId(et) AS id, et.name AS name, et.category AS category, fr.rule AS rule
    """)
    
    print("Generating rich embeddings for ErrorType nodes...")
    for record in error_types:
        # We combine name, category, and the rule text to create a highly semantic vector!
        text_to_embed = f"Error Type: {record['name']}. Category: {record['category']}. Rule: {record['rule']}"
        vector = embedder.embed_query(text_to_embed)
        
        session.run("""
        MATCH (et:ErrorType) WHERE elementId(et) = $id
        SET et.embedding = $vector
        """, {"id": record["id"], "vector": vector})

print("\nDatabase indexes successfully configured with rich Semantic Memory!")
driver.close()