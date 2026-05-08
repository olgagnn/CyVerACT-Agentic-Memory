''' Return the generated query'''
from Nodes.States.states import  OverallState, OutputState

# Importing Hybrid Memory Manager
# try:
#     from Memory.hybrid_manager import HybridMemoryManager
#     hybrid_memory = HybridMemoryManager()
#     memory_available = True
#     print("[Output Generator] Hybrid Memory Loaded")
# except ImportError:
#     print("[Output Generator] WARNING: HybridMemoryManager not found.")
#     memory_available = False

def output_generator(state: OverallState) -> OutputState:
    """
    Returns the final query based on the user question and the retieved results.
    """
    print('Output Generator: START')

    # Getting state results
    database_records = state.get("database_records")
    cypher_statement = state.get("cypher_statement")

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

    # STORING EPISODIC MEMORY (GRAPHITI)

    # if memory_available:
    #     try:
    #         # Truncating the answer -- update this later maybe we need it whole?
    #         short_answer = answer[:200] + "... [Truncated due to length]" if len(answer) > 200 else answer
            
    #         hybrid_memory.add_episodic_interaction(
    #             question=state.get("question"),
    #             final_cypher=cypher_statement,
    #             result=short_answer,
    #             errors=None,  # No errors since we're atp
    #             attempts=len(state.get("internal_cypher_errors_history", [])) if state.get("internal_cypher_errors_history") else 0
    #         )
    #         print("[Output Generator] Episodic memory saved successfully!")
    #     except Exception as e:
    #         print(f"[Output Generator] Memory save failed: {e}")

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