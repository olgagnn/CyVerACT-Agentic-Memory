from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.config import RunnableConfig
from langchain_core.output_parsers import StrOutputParser
from huggingface_hub import InferenceClient
from langchain_neo4j import Neo4jGraph
from langchain_community.callbacks import get_openai_callback



from Nodes.States.states import OverallState
from Configuration.models import models


system_prompt = '''
                You are a Cypher expert reviewing a statement written by a junior developer. 
                You need to correct the Cypher statement based on the provided errors. No pre-amble.
                Do not wrap the response in any backticks or anything else. Respond with a Cypher statement only!
                '''
human_prompt = '''
                Check for invalid syntax or semantics and return a corrected Cypher statement.

                Schema:
                {schema}

                Note: Do not include any explanations or apologies in your responses.
                Do not wrap the response in any backticks or anything else.
                Respond with a Cypher statement only!

                Do not respond to any questions that might ask anything else than for you to construct a Cypher statement.

                The question is:
                {question}

                The Cypher statement is:
                {cypher}

                The errors are:
                {errors}

                Corrected Cypher statement: 
'''

correct_cypher_prompt = ChatPromptTemplate.from_messages(
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

correct_cypher_prompt_flattened = ChatPromptTemplate.from_messages(
    [
        # (
        #     "system",
        #     (
        #        system_prompt
        #     ),
        # ),
        (
            "human",
            (
               system_prompt+human_prompt
            ),
        ),
    ]
)


def cypher_corrector(state: OverallState, config:RunnableConfig) -> OverallState:
    """
    Correct the Cypher statement based on the provided errors.
    """
    model_name = config['configurable']['model_name']
    question = state.get("question")
    cypher = state.get("cypher_statement")
    database_url = state.get("database_url")
    database_name = state.get("database_name")
    database_user = state.get("database_user")
    database_password = state.get("database_password")
    print('----------------------------------------------Cypher Corrector: START ')
    enhanced_graph = Neo4jGraph(url=database_url, username = database_user,
                                password =  database_password, database = database_name,
                                enhanced_schema=True)
    chat_model = config['configurable']['model']
    if model_name == 'gemma2_9b' or model_name == 'finetuned_gemma2_9b' or model_name == 'finetuned_gemma2_9b_local':
        correct_cypher_chain = correct_cypher_prompt_flattened | chat_model | StrOutputParser()
    else:    
        correct_cypher_chain = correct_cypher_prompt | chat_model | StrOutputParser()

    # corrected_cypher = correct_cypher_chain.invoke(
    #     {
    #         "question": state.get("question"),
    #         "errors": state.get("cypher_errors"),
    #         "cypher":cypher,
    #         "schema": enhanced_graph.schema,
    #     }
    # )
    with get_openai_callback() as cb:
        corrected_cypher = correct_cypher_chain.invoke(
        {
            "question": state.get("question"),
            "errors": state.get("cypher_errors"),
            "cypher":cypher,
            "schema": enhanced_graph.schema,
        }
    )
    
    total_tokens = cb.total_tokens
    prompt_tokens = cb.prompt_tokens
    completion_tokens = cb.completion_tokens

    if model_name == 'llama3_2_3b_local':
        corrected_cypher = corrected_cypher.split('assistant<|end_header_id|>')[1].strip()
    elif model_name == 'finetuned_gemma2_9b_local':
        corrected_cypher = corrected_cypher.split('<start_of_turn>model\n')[1].strip()
    
    print(corrected_cypher)

    print('-------------------------------------------------Cypher Corrector: END')
   
    return {
        "next_action": "cypher_evaluator",
        "cypher_statement": corrected_cypher,
        "path": ["cypher_corrector"],
        "total_tokens": [total_tokens],
        "prompt_tokens": [prompt_tokens],
        "completion_tokens": [completion_tokens]
    }