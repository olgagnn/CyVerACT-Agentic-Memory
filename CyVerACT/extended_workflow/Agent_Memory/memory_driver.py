from neo4j import GraphDatabase
from dotenv import load_dotenv
import os

load_dotenv(override=True)

def get_memory_driver():
    return GraphDatabase.driver(
        os.getenv("NEO4J_URI"),
        auth=(
            os.getenv("NEO4J_USERNAME"),
            os.getenv("NEO4J_PASSWORD")
        )
    )