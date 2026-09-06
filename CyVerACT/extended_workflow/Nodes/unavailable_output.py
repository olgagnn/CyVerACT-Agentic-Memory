from Nodes.States.states import  OverallState, OutputState

def unavailable_output(state: OverallState) -> OutputState:
    """
    Returns the unavailable answer.
    """
    print('Unavailable Output: START')
    # print('Unavailable Output: END')
    # print()
    return {
        "path": ["unavailable_output"],
        "cypher_statement": state.get("cypher_statement"),
        "database_records": [''],
        'is_KG_Valid_correct': False,
        'answer': "I couldn't find any relevant information in the database", 
        'cypher_errors_history': state.get("internal_cypher_errors_history")   ,
        'cypher_errors': state.get("cypher_errors"),
        "total_tokens": [-1],
        "prompt_tokens": [-1],
        "completion_tokens": [-1]   
    }