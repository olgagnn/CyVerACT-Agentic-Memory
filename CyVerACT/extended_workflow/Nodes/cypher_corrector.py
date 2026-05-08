from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.config import RunnableConfig
from langchain_core.output_parsers import StrOutputParser
from huggingface_hub import InferenceClient
from langchain_community.callbacks import get_openai_callback


from Nodes.States.states import OverallState
# from Configuration.models import models

# Importing HYBRID MEMORY
# try:
#     from Memory.hybrid_manager import HybridMemoryManager
#     hybrid_memory = HybridMemoryManager()
#     memory_available = True
#     print("[Cypher Corrector] Hybrid Memory Loaded")
# except ImportError:
#     print("[Cypher Corrector] WARNING: HybridMemoryManager not found.")
#     memory_available = False

# Removed Previous Similar Mistakes & Lessons: {memory_context}

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

    # --- ADDED FOR SCSR METRIC ---
    attempts = state.get("attempts", 0)
    # memory_hit = False
    
    # memory_context = ""

    # if memory_available and cypher_errors_list:
    #     try:
    #         error_signature = " | ".join(cypher_errors_list)

    #         search_query = f"""
    #         Cypher mistake case.
    #         Errors: {error_signature}
    #         Faulty query: {cypher}
    #         """

    #         print("[Cypher Corrector] Searching procedural memory...")
    #         past_lessons = hybrid_memory.get_procedural_lessons(search_query)
    #         print(f"[Memory] Found past mistakes for similar queries!" + past_lessons) # for debugging 
    #         if past_lessons:
    #             memory_context = f"\nPrevious Similar Mistakes & Lessons:\n{past_lessons}\n"
    #             print("[Cypher Corrector] Found past lessons!")
    #             # --- ADDED FOR SCSR METRIC ---
    #             memory_hit = True
    #         else:
    #             print("[Cypher Corrector] No similar lessons found.")

    #     except Exception as e:
    #         print(f"[Cypher Corrector] Memory retrieval error: {e}")

    
    cypher_errors = "\n".join(
        f"{i + 1}. {error}" for i, error in enumerate(cypher_errors_list)
    )

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
                "errors": cypher_errors,
                #"memory_context": memory_context
                
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
        "completion_tokens": [completion_tokens],
        # --- ADDED FOR SCSR METRIC ---
        "attempts": attempts + 1
        # "memory_hit": memory_hit
    }

    
