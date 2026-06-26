from neo4j import GraphDatabase,basic_auth
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.config import RunnableConfig
from pydantic import BaseModel, Field
from typing import List, Optional
from langchain_openai import  ChatOpenAI
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
import os 

from Nodes.States.states import OverallState
import sys
# This adds the parent directory (../) to the list of directories Python will search for modules.
# The ../ refers to the directory one level up from the current working directory.
sys.path.append('../')
from CyVer_custom import SyntaxValidator,PropertiesValidator,SchemaValidator
# from models import models



evaluate_semantic_cypher_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "Given an input question and its Cypher query you evaluate if the Cypher query semantically alogns with the question."
                
            ),
        ),
        (
            "human",
            (
                """To evaluate the Cypher query you must check the following:
                * Does the Cypher query include enough information to answer the question?
                * Does the Cypher query include additional matches or fields that are not needed to answer the question?
                * Does the Cypher query answers the question?

               The question is:
                {question}

                The Cypher statement is:
                {cypher}
                
                """
            ),
        ),
    ]
)

class ValidateCypherOutput(BaseModel):
    """
    Pydantic model for the output data structure.
    Represents the validation result of a Cypher query's output,
    including any semantic errors.
    """

    semantic_errors: Optional[List[str]] = Field(
        description="A list of semantical errors in the Cypher statement. Always explain the discrepancy between schema and Cypher statement"
    )


#Create cypher evaluator node
def cypher_evaluator(state: OverallState, config:RunnableConfig) -> OverallState:
    
    cypher_statement = state.get("cypher_statement")
    # database_url = state.get("database_url")
    database_name = state.get("database_name")
    # database_user = state.get("database_user")
    # database_password = state.get("database_password")
    # Connect to the database
    # driver = GraphDatabase.driver(database_url, auth=basic_auth(database_user, database_password) )
    driver = state.get("neo4j_driver")

    # model_name = config['configurable']['model']
    # chat_model = models[model_name]
    # chat_model =  ChatOpenAI(
    #                             model="gpt-4o", 
    #                             temperature=0,
    #                             api_key= os.getenv('OPENAI_API_KEY'),
    #                         )
    # print('model selected:', model_name)
    
    #---------------CyVer evaluation------------------
    cypher_errors = []

 

    #SyntaxValidator
    syntax_validator =  SyntaxValidator(driver)
    syntax_valid, syntax_validation_metadata = syntax_validator.validate(cypher_statement, database_name=database_name)
   # if syntax_valid: #?
    #SchemaValidator
    schema_validator = SchemaValidator(driver)
    schema_valid, schema_validation_metadata = schema_validator.validate(cypher_statement, database_name=database_name)

    #PropertiesValidator
    properties_validator = PropertiesValidator(driver)
    properties_valid, properties_validation_metadata = properties_validator.validate(cypher_statement, database_name=database_name)

    
    if syntax_validation_metadata:
        for error in syntax_validation_metadata:
            cypher_errors.append(error['code']+': '+ error['description'])

    if schema_validation_metadata:
        for error in schema_validation_metadata:
            cypher_errors.append(error['code'] +': '+ error['description'])
    if properties_validation_metadata:
        for error in properties_validation_metadata:
            cypher_errors.append(error['code']+': '+  error['description'])
            
    # if cypher_errors:
    #     print('CyVer Errors from generated query:')
    #     for error in cypher_errors:
    #         print('-', error)
    #         print()
    #     # next_action = "cypher_corrector"
    # else:
    #     print('No CyVer Errors from generated query.')
    # print('---------------------------------')
        # next_action = "cypher_executor"


    #---------------------LLM semantic evaluation-------------------
    # semantic_evaluation_chain = evaluate_semantic_cypher_prompt | chat_model.with_structured_output(
    #                                                                         ValidateCypherOutput
    #                                                                     )
    # validation_output = semantic_evaluation_chain.invoke(
    #     {
    #         "question": state.get("question"),
    #         "cypher": state.get("cypher_statement"),
    #     }
    # )
    # if validation_output.semantic_errors:
    #     print('Semantic Errors in generated query:')
    #     for error in  validation_output.semantic_errors:
    #         print('-', error)
    #         print()
    #     cypher_errors.extend(validation_output.semantic_errors)
        
    # else:
    #     print('No semantic errors in generated query.')

    if cypher_errors:
        next_action = "cypher_corrector"
    else:
        next_action = "cypher_executor"
    return{
        'next_action': next_action,
        'cypher_errors': cypher_errors,
        'path':['cypher_evaluator'],
        'cypher_errors_history':[cypher_errors],
        "total_tokens": [-1],
        "prompt_tokens": [-1],
        "completion_tokens": [-1]
    }