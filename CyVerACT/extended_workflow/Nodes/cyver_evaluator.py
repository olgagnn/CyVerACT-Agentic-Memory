from neo4j import GraphDatabase,basic_auth
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.config import RunnableConfig
import os 
from collections import Counter
from Nodes.States.states import OverallState

import sys
# This adds the parent directory (../) to the list of directories Python will search for modules.
# The ../ refers to the directory one level up from the current working directory.
sys.path.append('../')
from CyVer_custom import SyntaxValidator,PropertiesValidator,SchemaValidator
#from CyVer import SyntaxValidator,PropertiesValidator,SchemaValidator
# IMPORT MEMORY MANAGER
from Agent_Memory.memory_manager import MemoryManager

from Agent_Memory.memory_driver import get_memory_driver

from langchain_huggingface import HuggingFaceEmbeddings

# Initialize the embedder locally
embedder = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

#Create cypher evaluator node
def cyver_evaluator(state: OverallState, config:RunnableConfig) -> OverallState:
    
    cypher_statement = state.get("cypher_statement")
    # database_url = state.get("database_url")
    database_name = state.get("database_name")
    # database_user = state.get("database_user")
    # database_password = state.get("database_password")
    total_attempts = config['configurable']['total_attempts']
    attempts_w_filtered = config['configurable']['attempts_w_filtered']

    # GET QUESTION FROM STATE
    question = state.get("question")

    # # Connect to the database
    driver = state.get("neo4j_driver")
    # driver = GraphDatabase.driver(database_url, auth=basic_auth(database_user, database_password) )

    #---------------CyVer evaluation------------------
    print('CyVer Evaluator: START')
    print('CyVer Evaluation of {}:'.format(cypher_statement))

    cypher_errors = []
    # COLLECT RAW METADATA FOR MEMORY WRITING
    raw_metadata_collection = []  
   
    #SyntaxValidator
    syntax_validator =  SyntaxValidator(driver)
    _, syntax_validation_metadata = syntax_validator.validate(cypher_statement, database_name=database_name)

    #SchemaValidator
    schema_validator = SchemaValidator(driver)
    _, schema_validation_metadata = schema_validator.validate(cypher_statement, database_name=database_name)

    #PropertiesValidator
    properties_validator = PropertiesValidator(driver)
    _, properties_validation_metadata = properties_validator.validate(cypher_statement, database_name=database_name)

    
    if syntax_validation_metadata:
        for error in syntax_validation_metadata:
            cypher_errors.append(error['code']+': '+ error['description'])
            raw_metadata_collection.append(error) # MEMORY

    if schema_validation_metadata:
        for error in schema_validation_metadata:
            cypher_errors.append(error['code'] +': '+ error['description'])
            raw_metadata_collection.append(error) # MEMORY

    if properties_validation_metadata:
        for error in properties_validation_metadata:
            cypher_errors.append(error['code']+': '+  error['description'])
            raw_metadata_collection.append(error) # MEMORY

    # MEMORY - Calculate sequential attempt number based on the execution history
    current_attempt_num = len(state.get("cypher_history", [])) 
    
    # ========================================================
    # LONG-TERM MEMORY STORAGE: Writing execution record to Neo4j
    # ========================================================
    save_flag = state.get("save_to_memory", True)
    
    if save_flag:
        memory_driver = get_memory_driver()
        try:
            memory_manager = MemoryManager(memory_driver)
            memory_manager.store_attempt(
                question=question,
                cypher=cypher_statement,
                raw_errors=raw_metadata_collection,
                attempt_num=current_attempt_num,
                embedder=embedder
            )
        finally:
            memory_driver.close()
    else:
        print("\n[MEMORY MANAGER] save_to_memory is FALSE. Skipping error recording.\n")
    
    current_path = state.get("path", [])
    frequency = Counter(current_path)

    if cypher_errors:
        # print('CyVer Evaluation of {}'.format(cypher_statement))
        print('CyVer Errors from generated query:')
        for error in cypher_errors:
            print('-', error)
            print()
        # If Cypher Corrector exists in the path more than n times then:
        if frequency['cypher_corrector'] == attempts_w_filtered:
            # If the second to last elemet is schema retriever (it means that the schema filtering has failed and
            # also exists errors, so we need to go to the cypher_corrector to increase the frequency)
            if current_path[-2]=='schema_retriever':
                # print('Starting Cypher Corrector with Full Schema')
                next_action = "cypher_corrector"
            # Else, meaning that the second to last element is cypher corrector, then we need to go to the schema retriever
            # to access the full schema
            else:
                # print('Failed to give a executable query, go to the Schema Retriever')
                # print('Returning to Schema Retriever.')
                next_action = "schema_retriever"
        # If Cypher Corrector exists in the path more than k times then we need to end the workflow and give unavailable output.
        elif frequency['cypher_corrector'] == total_attempts:
            # print('Failed to give a executable query, go to the Unavailable Output')
            next_action = "unavailable_output"
        # Else if frequency<n or n<frequency<k then we need to go to the cypher corrector
        else:
            next_action = "cypher_corrector"
    # Else, if there are no errors, we need to go to the cypher executor
    else:
        next_action = "cypher_executor"
        
        # print(cypher_statement)
        # print('No CyVer Errors from generated query.')
    
    # print('CyVer Evaluator: END')
    # print()

    # MEMORY 
    current_error = cypher_errors[0] if cypher_errors else ""
    return{
        'next_action': next_action,
        'cypher_errors': cypher_errors,
        'current_error': current_error,   # MEMORY
        'path':['cyver_evaluator'],
        'internal_cypher_errors_history':[cypher_errors],
        "total_tokens": [-1],
        "prompt_tokens": [-1],
        "completion_tokens": [-1]
        }    