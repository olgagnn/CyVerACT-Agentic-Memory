from neo4j_graphrag.schema import get_structured_schema
from neo4j import GraphDatabase,basic_auth

from Nodes.States.states import InputState, OverallState
import os
import json
import sys
# This adds the parent directory (../) to the list of directories Python will search for modules.
# The ../ refers to the directory one level up from the current working directory.
sys.path.append('../')
from utils.KG_schema_formatting import format_final_schema,get_structured_schema_custom
from utils.access_precomputed import get_kg_schema, save_kg_schema

KG_schema_json_path = os.path.abspath(os.path.join("..", "precomputed", "KG_schemas", "kg_schema.json"))
KG_structured_schema_json_path = os.path.abspath(os.path.join("..", "precomputed", "KG_schemas", "kg_structured_schema.json"))


def schema_retriever(state: InputState) -> OverallState:
    """
    Gets the schema from the database. 
    """

    database_url = state.get("database_url")
    database_name = state.get("database_name")
    database_user = state.get("database_user")
    database_password = state.get("database_password")

    #Connect to the database
    driver = GraphDatabase.driver(database_url, auth=basic_auth(database_user, database_password) )

    # Try to load the KG schema for the given database_name from kg_schema.json
    schema = get_kg_schema(database_name, KG_schema_json_path)
    if not schema:
        # Try to load the KG schema for the given database_name from  kg_structured_schema.json
        structured_schema = get_kg_schema(database_name, KG_structured_schema_json_path)
        if not structured_schema:
            # structured_schema = get_structured_schema(driver, is_enhanced = False, database = database_name, sanitize = False)
            structured_schema = get_structured_schema_custom(driver, is_enhanced = False, database = database_name, sanitize = False)
            save_kg_schema(database_name, structured_schema, KG_structured_schema_json_path)
       
       
        # schema = get_schema(driver, is_enhanced = False, database = database_name, sanitize = False)
        schema = format_final_schema(driver, database_name, structured_schema, structured_schema, inline_props=True)

        save_kg_schema(database_name, schema, KG_schema_json_path)

    # print(schema)
    return {"schema": schema, 
            "path": ["schema_retriever"]}