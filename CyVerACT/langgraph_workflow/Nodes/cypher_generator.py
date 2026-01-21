from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.config import RunnableConfig
from Nodes.States.states import  OverallState
from langchain_neo4j import Neo4jGraph
from langchain.callbacks import get_openai_callback


system_prompt = """
    Given an input question, convert it to a Cypher query. No pre-amble.
    Do not wrap the response in any backticks or anything else. Respond with a Cypher statement only!
"""
human_prompt = """
    You are a Neo4j expert. Given an input question, create a syntactically correct Cypher query to run.
    Do not wrap the response in any backticks or anything else. Respond with a Cypher statement only!
    Here is the schema information
    {schema}


    User input: {question}
    Cypher query:
"""
text2cypher_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
              system_prompt
            ),
        ),
        (
            "human",
            (
                human_prompt
            ),
        ),
    ]
)

text2cypher_prompt_flattened = ChatPromptTemplate.from_messages(
    [
        # (
        #     "system",
        #     (
        #       system_prompt
        #     ),
        # ),
        (
            "human",
            (
                system_prompt + human_prompt
            ),
        ),
    ]
)




def cypher_generator(state: OverallState, config:RunnableConfig) -> OverallState:
    """
    Generates a cypher statement based on the provided schema and user input
    """
    print('--------------------------------------------------Cypher Generator: START')
    model_name = config['configurable']['model_name']
    question = state.get("question")
    database_url = state.get("database_url")
    database_name = state.get("database_name")
    database_user = state.get("database_user")
    database_password = state.get("database_password")

    enhanced_graph = Neo4jGraph(url=database_url, username = database_user,
                                password =  database_password, database = database_name,
                                enhanced_schema=True)
    schema = enhanced_graph.schema
    # print('Database Schema:',schema)

    chat_model = config['configurable']['model']

    
    if model_name == 'gemma2_9b' or model_name == 'finetuned_gemma2_9b' or model_name =='finetuned_gemma2_9b_local':
        text2cypher_chain = text2cypher_prompt_flattened | chat_model | StrOutputParser()
    else:    
        text2cypher_chain = text2cypher_prompt | chat_model | StrOutputParser()

    with get_openai_callback() as cb:
        generated_cypher = text2cypher_chain.invoke({
            "question": question,
            "schema": schema,
        })

    total_tokens = cb.total_tokens
    prompt_tokens = cb.prompt_tokens
    completion_tokens = cb.completion_tokens

    # generated_cypher = text2cypher_chain.invoke(
    #     {
    #         "question": question,
    #         "schema": schema,
    #     }
    # )
    if model_name == 'llama3_2_3b_local':
        generated_cypher = generated_cypher.split('assistant<|end_header_id|>')[1].strip()
    elif model_name == 'finetuned_gemma2_9b_local':
        generated_cypher = generated_cypher.split('<start_of_turn>model\n')[1].strip()

    
    print(generated_cypher)
    print('-------------------------------Cypher Generator: END')
    
    return {"cypher_statement": generated_cypher, 
            "schema": schema,
            "path": ["cypher_generator"],
            "total_tokens": [total_tokens],
            "prompt_tokens": [prompt_tokens],
            "completion_tokens": [completion_tokens]}