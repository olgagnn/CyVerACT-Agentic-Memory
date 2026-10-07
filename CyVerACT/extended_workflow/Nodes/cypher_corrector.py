from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.config import RunnableConfig
from langchain_core.output_parsers import StrOutputParser
from huggingface_hub import InferenceClient
from langchain_community.callbacks import get_openai_callback

from Nodes.States.states import OverallState
# from Configuration.models import models

# IMPORT MEMORY MANAGER
from Agent_Memory.memory_manager import MemoryManager
from Agent_Memory.memory_driver import get_memory_driver

# MEMORY EMBEDDINGS
from langchain_huggingface import HuggingFaceEmbeddings

# INITIALIZE HERE (Outside the function so it doesn't reload on every single retry loop) 

# REMOVED     

embedder = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
                
system_prompt = '''
                You are a Cypher expert reviewing a statement. 
                Given an input Cypher statement and the errors it has, correct the Cypher statement.  No pre-amble.
                Do not wrap the response in any backticks or anything else. Respond with a Cypher statement only!
            '''

human_prompt = '''
                Fix the Cypher statement based on the given errors.
                The Cypher statement should be valid for the given knowledge graph schema. 
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

                Previous Attempts and Their Outcomes:
                {history}
                
                {trajectory_context}
                
                {rules_context}

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
    """
    model_name = config['configurable']['model_name']
    question = state.get("question")
    cypher = state.get("cypher_statement")
    schema = state.get("schema")
    cypher_errors_list = state.get("cypher_errors")
    cypher_errors = "\n".join(
        f"{i + 1}. {error}" for i, error in enumerate(cypher_errors_list)
    )

    # ========================================================
    # SHORT-TERM MEMORY: History (COMPRESSED)
    # ========================================================
    cypher_history = state.get("cypher_history", [])
    errors_history = state.get("internal_cypher_errors_history", [])
    
    # State lists into the format MemoryManager expects
    attempts_list = []
    for i in range(len(cypher_history) - 1):
        past_cypher = cypher_history[i]
        past_errors = errors_history[i] if i < len(errors_history) else []

        attempts_list.append({
            "attempt_num": i + 1,
            "cypher": past_cypher,
            "errors": past_errors
        })

    # Compress previous attempts for prompt context
    if attempts_list:
        history_str = MemoryManager.compress_short_term_history_prompt(attempts_list)
    else:
        history_str = "No previous failed attempts."

    # ========================================================
    # LONG-TERM MEMORY RETRIEVAL: Fetch generic + specific instructions 
    # ========================================================
    memory_driver = get_memory_driver()
    try:
        memory_manager = MemoryManager(memory_driver)
        
        # Fix Rules
        fix_rules = memory_manager.get_fix_rules(cypher_errors_list)
        
        # Episodic Trajectory Injection
        primary_error = cypher_errors_list[0] if cypher_errors_list else ""
        
        # Pass the current question and the failed cypher along with the error
        trajectory_data = memory_manager.get_trajectory_fix_context(question, cypher, primary_error, embedder, limit=1) if primary_error else ""
        
    finally:
        memory_driver.close()
      
    # Process Generic Rules
    if fix_rules:
        print("\n[MEMORY MANAGER] Triggered! Retrieved the following FixRules:")
        for rule in fix_rules:
            print(f"   -> {rule}")
        print() 
        
        rules_context = (
            "Generic Repair Principles:\n"
            + "\n".join([f"- {rule}" for rule in fix_rules])
            + "\n"
        )
    else:
        print("\n[MEMORY MANAGER] No matching FixRules found in database for these errors.\n")
        rules_context = ""

    # Process Episodic Trajectory
    if trajectory_data:
        print("\n[MEMORY MANAGER] Triggered! Retrieved Episodic Trajectory Data:")
        print("-" * 40)
        print(trajectory_data) 
        print("-" * 40 + "\n")
        trajectory_context = f"Review the following context and structural guidance to resolve the error:\n{trajectory_data}\n"
    else:
        trajectory_context = ""
    
    chat_model = config['configurable']['model']
    
    if model_name == 'gemma2_9b' or model_name == 'finetuned_gemma2_9b' or model_name == 'finetuned_gemma2_9b_local':
        fix_cypher_chain = fix_cypher_prompt_flattened | chat_model | StrOutputParser()
    else:    
        fix_cypher_chain = fix_cypher_prompt | chat_model | StrOutputParser()

    print("\n" + "="*50)
    print("[MEMORY MANAGER] Error History:")
    print(history_str)
    print("="*50 + "\n")
    
    with get_openai_callback() as cb:
        corrected_cypher = fix_cypher_chain.invoke(
            {
                "question": question,
                "schema": schema,
                "cypher": cypher,
                "errors": cypher_errors,
                "rules_context": rules_context, 
                "trajectory_context": trajectory_context,
                "history": history_str 
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
    return {
        'next_action': 'cypher_evaluator',
        'cypher_statement': corrected_cypher,
        'path': ['cypher_corrector'],
        "total_tokens": [total_tokens],
        "prompt_tokens": [prompt_tokens],
        "completion_tokens": [completion_tokens],
        'cypher_history': [corrected_cypher], 
        "history": history_str,
    }