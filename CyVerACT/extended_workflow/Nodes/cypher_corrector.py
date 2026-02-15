from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.config import RunnableConfig
from langchain_core.output_parsers import StrOutputParser
from huggingface_hub import InferenceClient
from langchain_community.callbacks import get_openai_callback


from Nodes.States.states import OverallState
# from Configuration.models import models

# Importing Hybrid Memory Manager
try:
    from Memory.hybrid_manager import HybridMemoryManager
    # Initialize HYBRID MEMORY
    hybrid_memory = HybridMemoryManager()
    memory_available = True
    print("[Cypher Corrector] Hybrid Memory Loaded")
except ImportError:
    print("WARNING: HybridMemoryManager not found.")
    memory_available = False

system_prompt = '''
                You are a Cypher expert reviewing a statement. 
                Given an input Cypher statement and the errors it has, correct the Cypher statement.  No pre-amble.
                Do not wrap the response in any backticks or anything else. Respond with a Cypher statement only!
            '''
human_prompt = '''
                Fix the Cypher statememnt based on the given errors.
                The Cypher statement should valid for the given knowledge graph schema. 
                Use only the provided labels and relationship types and properties in the schema. 
                Do not use any other node labels, relationship types or properties that are not provided in the schema. 

                Schema:
                {schema}

                Note: Do not include any explanations or apologies in your responses.
                Do not wrap the response in any backticks or anything else.
                Respond with a Cypher statement only!

                The question is:
                {question}

                The Cypher statement is:
                {cypher}

                The errors for the Cypher statement are:
                {errors}

                Corrected Cypher statement:
        
                '''

fix_cypher_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (system_prompt
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

fix_cypher_prompt_flattened = ChatPromptTemplate.from_messages(
    [
        # (
        #     "system",
        #     (system_prompt
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

def cypher_corrector(state: OverallState, config:RunnableConfig) -> OverallState:
    """
    Correct the Cypher statement based on the provided errors.
    Also store the error in Hybrid Memory (Cognee) for future learning.
    """
    model_name = config['configurable']['model_name']
    question = state.get("question")
    cypher = state.get("cypher_statement")
    schema = state.get("schema")
    cypher_errors_list = state.get("cypher_errors")
    cypher_errors = "\n".join(
        f"{i + 1}. {error}" for i, error in enumerate(cypher_errors_list)
    )

    # Store to memory and LEARN !!! 
    # Corrector should correct current error and store info in order not to repeat it
    if memory_available and cypher_errors_list:
        try:
            print(f"[Cypher Corrector] Storing mistake in Hybrid Memory (Cognee)...")
            hybrid_memory.add_error_lesson(
                query=question,
                bad_cypher=cypher,
                error_msg=cypher_errors 
            )
        except Exception as e:
            print(f"[Memory] Failed to save error: {e}")

    chat_model = config['configurable']['model']
    
    if model_name == 'gemma2_9b' or model_name == 'finetuned_gemma2_9b' or model_name == 'finetuned_gemma2_9b_local':
        fix_cypher_chain = fix_cypher_prompt_flattened | chat_model | StrOutputParser()
    else:    
        fix_cypher_chain = fix_cypher_prompt | chat_model | StrOutputParser()

    
    with get_openai_callback() as cb:
        corrected_cypher = fix_cypher_chain.invoke(
            {
                "question": question,
                "schema": schema,
                "cypher": cypher,
                "errors": cypher_errors
            }
        )
    
    total_tokens = cb.total_tokens
    prompt_tokens = cb.prompt_tokens
    completion_tokens = cb.completion_tokens

    if model_name == 'llama3_2_3b_local':
        corrected_cypher = corrected_cypher.split('assistant<|end_header_id|>')[1].strip()
    elif model_name == 'finetuned_gemma2_9b_local':
        corrected_cypher = corrected_cypher.split('<start_of_turn>model\n')[1].strip()

    print('Cypher Corrector: START')
    # print('The selected model is ', model_name)
    # print('Corrected Cypher statement: \n {}'.format(corrected_cypher))
    # # print(corrected_cypher)
    # print('Cypher Corrector: END')
    # print()
    return {
        'next_action': 'cypher_evaluator',
        'cypher_statement': corrected_cypher,
        'path': ['cypher_corrector'],
        "total_tokens": [total_tokens],
        "prompt_tokens": [prompt_tokens],
        "completion_tokens": [completion_tokens]
    }

    
