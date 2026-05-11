''' Return the generated query'''
from Nodes.States.states import  OverallState, OutputState
import os

# Init Custom Memory
from Agent_Memory.custom_cyver_memory import CyVerMemory

URI = os.getenv("NEO4J_URI")
USER = os.getenv("NEO4J_USERNAME")
PASSWORD = os.getenv("NEO4J_PASSWORD")
DB_NAME = os.getenv("MEMORY_DATABASE")

memory = CyVerMemory(
    URI,
    USER,
    PASSWORD,
    database=DB_NAME
)

def output_generator(state: OverallState) -> OutputState:
    """
    Returns the final query based on the user question and the retieved results.
    """
    print('Output Generator: START')

    # Getting state results
    database_records = state.get("database_records")
    cypher_statement = state.get("cypher_statement")
    question = state.get("question") # Needed for memory
    session_id = state.get("session_id", "default_session") # Needed for memory

    if database_records and len(database_records) > 0:
        # Results to string 
        formatted_list = []
        for rec in database_records:
            entry = ", ".join([f"{k}: {v}" for k, v in rec.items()])
            formatted_list.append(entry)
        
        results_str = " | ".join(formatted_list)
        answer = f"I found the following in the database: {results_str}"
        path_step = "output_generator"
    else:
        answer = "I couldn't find any relevant information in the database."
        path_step = "unavailable_output"

    print(f"Agent Answer: {answer}")

    # CONTEXT GRAPH MEMORY (EPISODIC)
    try:
        memory.add_episodic_memory(
            user_id=state.get("user_id", "default_user"),
            session_id=session_id,
            user_question=question,
            agent_answer=answer
        )
        print("[Memory] Episodic memory stored successfully.")
    except Exception as e:
        print(f"[Memory] Failed to save episodic memory: {e}")

    print('Output Generator: END')
    
    return {
        "path": ["output_generator"],
        "cypher_statement": state.get("cypher_statement"),
        "database_records": state.get("database_records"),
        "answer": answer,
        'is_KG_Valid_correct':True,
        'cypher_errors_history': state.get("internal_cypher_errors_history"),
        'cypher_errors': [],
        "total_tokens": [-1],
        "prompt_tokens": [-1],
        "completion_tokens": [-1]  
    }