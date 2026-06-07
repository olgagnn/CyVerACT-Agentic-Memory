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
embedder = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

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

                === PREVIOUS FAILED ATTEMPTS (DO NOT REPEAT THESE CYpher STATEMENTS) ===
                {history}
                ========================================================================

                The Cypher statement is:
                {cypher}

                The errors for the Cypher statement are:
                {errors}

                {dynamic_rules_section}

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
    # SHORT-TERM MEMORY: Trajectory History 
    # ========================================================
    cypher_history = state.get("cypher_history", [])
    errors_history = state.get("internal_cypher_errors_history", [])
    
    history_str = ""
    # We iterate up to len-1 because the very last item in the history 
    # is the 'current' failed attempt being evaluated below!
    for i in range(len(cypher_history) - 1):
        history_str += f"Attempt {i+1}:\n"
        history_str += f"Cypher: {cypher_history[i]}\n"
        
        # Guard against index out of bounds just in case the arrays get misaligned
        if i < len(errors_history):
            past_errors = "\n".join([f"  - {err}" for err in errors_history[i]])
            history_str += f"Errors:\n{past_errors}\n"
        history_str += "-" * 40 + "\n"

    if not history_str.strip():
        history_str = "No previous failed attempts."

    # ========================================================
    # LONG-TERM MEMORY RETRIEVAL: Fetch generic + specific instructions 
    # ========================================================
    memory_driver = get_memory_driver()
    try:
        memory_manager = MemoryManager(memory_driver)
        fix_rules = memory_manager.get_fix_rules_vector_search(cypher_errors_list, embedder)
    finally:
        memory_driver.close()
    
    if fix_rules:
        print("\n[MEMORY MANAGER] Triggered! Retrieved the following FixRules:")
        for rule in fix_rules:
            print(f"   -> {rule}")
        print() # readability
        
        rules_str = "\n".join(f"- {rule}" for rule in fix_rules)
        dynamic_rules_section = f"Crucial Rules to follow for this specific fix:\n{rules_str}\n"
    else:
        print("\n[MEMORY MANAGER] No matching FixRules found in database for these errors.\n")
        dynamic_rules_section = ""
    
    chat_model = config['configurable']['model']
    
    if model_name == 'gemma2_9b' or model_name == 'finetuned_gemma2_9b' or model_name == 'finetuned_gemma2_9b_local':
        fix_cypher_chain = fix_cypher_prompt_flattened | chat_model | StrOutputParser()
    else:    
        fix_cypher_chain = fix_cypher_prompt | chat_model | StrOutputParser()

    # Prints for memory 
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
                "dynamic_rules_section": dynamic_rules_section,  # MEMORY
                "history": history_str # MEMORY
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
        'cypher_history': [corrected_cypher], # MEMORY
        "history": history_str  # MEMORY TRAJECTORY HERE
    }