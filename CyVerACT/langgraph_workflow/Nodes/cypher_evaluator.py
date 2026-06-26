from typing import List, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel, Field
from langchain_neo4j.chains.graph_qa.cypher_utils import CypherQueryCorrector, Schema
from collections import Counter

from langchain_core.runnables.config import RunnableConfig
from Nodes.States.states import  OverallState
from langchain_neo4j import Neo4jGraph


validate_cypher_system = """
You are a Cypher expert reviewing a statement written by a junior developer.
"""

validate_cypher_user = """You must check the following:
        * Are there any syntax errors in the Cypher statement?
        * Are there any missing or undefined variables in the Cypher statement?
        * Are any node labels missing from the schema?
        * Are any relationship types missing from the schema?
        * Are any of the properties not included in the schema?
        * Does the Cypher statement include enough information to answer the question?

        Examples of good errors:
        * Label (:Foo) does not exist, did you mean (:Bar)?
        * Property bar does not exist for label Foo, did you mean baz?
        * Relationship FOO does not exist, did you mean FOO_BAR?

        Schema:
        {schema}

        The question is:
        {question}

        The Cypher statement is:
        {cypher}

        Make sure you don't make any mistakes!

        List all the errors you find in the Cypher statement. If there are no errors, respond with an empty list.
        Errors:
"""

validate_cypher_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            validate_cypher_system,
        ),
        (
            "human",
            (validate_cypher_user),
        ),
    ]
)

validate_cypher_prompt_flattened = ChatPromptTemplate.from_messages(
    [
        # (
        #     "system",
        #     validate_cypher_system,
        # ),
        (
            "human",
            (validate_cypher_system + validate_cypher_user),
        ),
    ]
)
class Property(BaseModel):
    """
    Represents a filter condition based on a specific node property in a graph in a Cypher statement.
    """

    node_label: str = Field(
        description="The label of the node to which this property belongs."
    )
    property_key: str = Field(description="The key of the property being filtered.")
    property_value: str = Field(
        description="The value that the property is being matched against."
    )


class ValidateCypherOutput(BaseModel):
    """
    Represents the validation result of a Cypher query's output,
    including any errors and applied filters.
    """

    errors: Optional[List[str]] = Field(
        description="A list of syntax or semantical errors in the Cypher statement. Always explain the discrepancy between schema and Cypher statement"
    )
    filters: Optional[List[Property]] = Field(
        description="A list of property-based filters applied in the Cypher statement."
    )






from neo4j.exceptions import CypherSyntaxError


def cypher_evaluator(state: OverallState, config:RunnableConfig) -> OverallState:
    """
    Validates the Cypher statements and maps any property values to the database.
    """
    model_name = config['configurable']['model_name']
    question = state.get("question")
    cypher_statement = state.get("cypher_statement")
    database_url = state.get("database_url")
    database_name = state.get("database_name")
    database_user = state.get("database_user")
    database_password = state.get("database_password")
    attempts = config['configurable']['attempts']

    current_path = state.get("path", [])
    frequency = Counter(current_path)
    print('Current frequency of nodes in the path:', frequency)
    

    enhanced_graph = Neo4jGraph(url=database_url, username = database_user,
                                password =  database_password, database = database_name,
                                enhanced_schema=True)


    errors = []
    print('----------------------------------------------Cypher Evaluator:START ')
    mapping_errors = []
    # 1.Check for syntax errors
    print('-----------------------------------------Checking for syntax errors...')
    try:
        enhanced_graph.query(f"EXPLAIN {cypher_statement}")
    except CypherSyntaxError as e:
        errors.append(e.message)
    
    #2. Experimental feature for correcting relationship directions
    print('-----------------------------------------Checking for relationship direction errors...')
    corrector_schema = [
        Schema(el["start"], el["type"], el["end"])
        for el in enhanced_graph.structured_schema.get("relationships")
    ]
    cypher_query_corrector = CypherQueryCorrector(corrector_schema)

    corrected_cypher = cypher_query_corrector(cypher_statement)
    if not corrected_cypher:
        errors.append("The generated Cypher statement doesn't fit the graph schema")
    if not corrected_cypher == cypher_statement:
        print("Relationship direction was corrected")
    
    #3. Use LLM to find additional potential errors and get the mapping for values
    print('-----------------------------------------Checking for additional errors with LLM...')
    llm = config['configurable']['model']


    if model_name == 'gemma2_9b' or model_name == 'finetuned_gemma2_9b' or model_name =='finetuned_gemma2_9b_local':
        # validate_cypher_chain = validate_cypher_prompt_flattened | llm | StrOutputParser()
        validate_cypher_chain = validate_cypher_prompt_flattened | llm.with_structured_output(
        ValidateCypherOutput
    )
    else:    
        # validate_cypher_chain = validate_cypher_prompt | llm | StrOutputParser()
        validate_cypher_chain = validate_cypher_prompt | llm.with_structured_output(
        ValidateCypherOutput
    )


    llm_output = validate_cypher_chain.invoke(
        {
            "question": question,
            "schema": enhanced_graph.schema,
            "cypher": cypher_statement,
        }
    )

    # if model_name == 'llama3_2_3b_local':
    #     llm_output = llm_output.split('assistant<|end_header_id|>')[1].strip()
    # elif model_name == 'finetuned_gemma2_9b_local':
    #     llm_output = llm_output.split('<start_of_turn>model\n')[1].strip()
    
    
    print('LLM output for Cypher evaluation:', llm_output)
    # if llm_output:
    #     errors.append(llm_output)
    if llm_output.errors:
        errors.extend(llm_output.errors)
    if llm_output.filters:
        print('Mapping property values for filters:', llm_output.filters)
        for filter in llm_output.filters:
            node_props = enhanced_graph.structured_schema.get("node_props", {}).get(filter.node_label, [])

            if not node_props:
                #Check if label exists in schema
                print(f"Label not found in schema: {filter.node_label}")
                errors.append(f"Label not found in schema: {filter.node_label}")
                continue

            prop_meta = next((p for p in node_props if p.get("property") == filter.property_key), None)

            if not prop_meta:
                print(f"Property {filter.property_key!r} not found in schema for {filter.node_label}. "
                    f"Available: {[p['property'] for p in node_props]}")
                errors.append(f" Property {filter.property_key!r} not found in schema for {filter.node_label}. "
                    f"Available: {[p['property'] for p in node_props]}")
                continue

            # Do mapping only for string values
            
            if str(prop_meta.get("type", "")).upper() != "STRING":
                print(f"Property {filter.property_key!r} on {filter.node_label} is {prop_meta['type']}, not STRING. Skipping.")
                continue

            # if (
            #     not [
            #         prop
            #         for prop in enhanced_graph.structured_schema["node_props"][
            #             filter.node_label
            #         ]
            #         if prop["property"] == filter.property_key
            #     ][0]["type"]
            #     == "STRING"
            # ):
            #     continue
            mapping = enhanced_graph.query(
                f"MATCH (n:{filter.node_label}) WHERE toLower(n.`{filter.property_key}`) = toLower($value) RETURN 'yes' LIMIT 1",
                {"value": filter.property_value},
            )
            if not mapping:
                print(
                    f"Missing value mapping for {filter.node_label} on property {filter.property_key} with value {filter.property_value}"
                )
                mapping_errors.append(
                    f"Missing value mapping for {filter.node_label} on property {filter.property_key} with value {filter.property_value}"
                )
    if mapping_errors:
        next_action = "unavailable_output" #"end"
        print('Maping Errors found in Cypher statement, moving to end:', mapping_errors)
    
    elif errors:
        if frequency['cypher_corrector'] == attempts:
            next_action = "unavailable_output"
            print('Maximum attempts reached. Moving to end.')
        else:
            next_action = "cypher_corrector"
            print('Errors found in Cypher statement:', errors)
    else:
        next_action = "cypher_executor"
    print(' ----------------------------------------------Cypher Evaluator: END')
    return {
        "next_action": next_action,
        "cypher_statement": corrected_cypher,
        "cypher_errors": errors,
        "path": ["cypher_evaluator"],
        "total_tokens": [-1],
        "prompt_tokens": [-1],
        "completion_tokens": [-1]
    }