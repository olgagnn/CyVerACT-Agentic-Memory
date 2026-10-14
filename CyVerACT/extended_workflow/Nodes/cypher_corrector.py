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

def cypher_corrector(state: OverallState, config:RunnableConfig) -> OverallState:
    """
    Correct the Cypher statement based on the provided errors.
    """
    model_name = config['configurable']['model_name']

    # Memory configuration
    use_history = config["configurable"].get("use_history", True)
    use_trajectory = config["configurable"].get("use_trajectory", True)
    use_fix_rules = config["configurable"].get("use_fix_rules", True)

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
    history_str = ""

    if use_history:
        cypher_history = state.get("cypher_history", [])
        errors_history = state.get("internal_cypher_errors_history", [])

        attempts_list = []

        for i in range(len(cypher_history) - 1):
            past_cypher = cypher_history[i]
            past_errors = errors_history[i] if i < len(errors_history) else []

            attempts_list.append({
                "attempt_num": i + 1,
                "cypher": past_cypher,
                "errors": past_errors
            })

        if attempts_list:
            history_str = MemoryManager.compress_short_term_history_prompt(
                attempts_list
            )
        else:
            history_str = "No previous failed attempts."

    # ========================================================
    # LONG-TERM MEMORY RETRIEVAL: Fetch generic + specific instructions 
    # ========================================================
    fix_rules = []
    trajectory_data = ""

    if use_fix_rules or use_trajectory:
        memory_driver = get_memory_driver()

        try:
            memory_manager = MemoryManager(memory_driver)

            # FixRules retrieval
            if use_fix_rules:
                fix_rules = memory_manager.get_fix_rules(cypher_errors_list)
                    
            # Trajectory retrieval
            if use_trajectory:
                primary_error = cypher_errors_list[0] if cypher_errors_list else ""

                if primary_error:
                    trajectory_data = memory_manager.get_trajectory_fix_context(
                        question, cypher, primary_error, embedder, limit=1
                    )

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
        if use_fix_rules:
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

    # Build prompt based on enabled memory mechanisms
    selected_human_prompt = human_prompt

    if not use_history:
        selected_human_prompt = selected_human_prompt.replace(
            "                Previous Attempts and Their Outcomes:\n"
            "                {history}\n"
            "                \n",
            ""
        )

    if not use_trajectory:
        selected_human_prompt = selected_human_prompt.replace(
            "                {trajectory_context}\n"
            "                \n",
            ""
        )

    if not use_fix_rules:
        selected_human_prompt = selected_human_prompt.replace(
            "                {rules_context}\n\n",
            ""
        )
    
    chat_model = config['configurable']['model']
    
    if model_name in {
    'gemma2_9b',
    'finetuned_gemma2_9b',
    'finetuned_gemma2_9b_local'
    }:
        selected_prompt = ChatPromptTemplate.from_messages([
            ("human", system_prompt + selected_human_prompt)
        ])
    else:
        selected_prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", selected_human_prompt)
        ])

    # Validate prompt variables for the selected configuration
    expected_variables = {"question", "schema", "cypher", "errors"}

    if use_history:
        expected_variables.add("history")

    if use_trajectory:
        expected_variables.add("trajectory_context")

    if use_fix_rules:
        expected_variables.add("rules_context")

    assert set(selected_prompt.input_variables) == expected_variables, (
        f"Unexpected prompt variables: {selected_prompt.input_variables}"
    )

    fix_cypher_chain = selected_prompt | chat_model | StrOutputParser()
    
    if use_history:
        print("\n" + "="*50)
        print("[MEMORY MANAGER] Error History:")
        print(history_str)
        print("="*50 + "\n")
    
    prompt_inputs = {
    "question": question,
    "schema": schema,
    "cypher": cypher,
    "errors": cypher_errors
    }

    if use_history:
        prompt_inputs["history"] = history_str

    if use_trajectory:
        prompt_inputs["trajectory_context"] = trajectory_context

    if use_fix_rules:
        prompt_inputs["rules_context"] = rules_context

    with get_openai_callback() as cb:
        corrected_cypher = fix_cypher_chain.invoke(prompt_inputs)
        
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
        'cypher_history': [corrected_cypher]
    }