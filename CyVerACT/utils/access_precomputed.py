import os
import json
def get_kg_schema(db_name, schema_file):
    ''' 
    Load the KG schema for a specific db_name from a JSON file.

    Args:
        db_name (str): The name of the database whose schema is to be retrieved.
        schema_file (str): Path to the JSON file containing KG schemas.

    Returns:
        str: The schema for the given db_name if found, else empty.
    '''
    if os.path.exists(schema_file):
        with open(schema_file, 'r') as f:
            try:
                kg_schemas = json.load(f)
                if db_name in kg_schemas:
                    return kg_schemas[db_name]
            except json.JSONDecodeError:
                return ""
    return ""

def save_kg_schema(db_name, schema, schema_file):
    '''
    Save or update the KG schema for a specific db_name into a JSON file.

    Args:
        db_name (str): The name of the database whose schema is to be saved.
        schema (dict): The schema data to save.
        schema_file (str): Path to the JSON file to update.
    '''
    # Load existing schemas if the file exists
    if os.path.exists(schema_file):
        with open(schema_file, 'r') as f:
            try:
                kg_schemas = json.load(f)
            except json.JSONDecodeError:
                kg_schemas = {}
    else:
        kg_schemas = {}

    # Update the schema for the specific db_name
    kg_schemas[db_name] = schema

    # Save updated schemas back to file
    with open(schema_file, 'w') as f:
        json.dump(kg_schemas, f, indent=2)