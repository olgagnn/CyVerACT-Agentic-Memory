from Nodes.States.states import  OverallState, OutputState

def unavailable_output(state: OverallState) -> OutputState:
    """
    Returns the unvailable answer.
    """
    print('Unvailable Output: START')
    # print('Unvailable Output: END')
    # print()
    return {
        "path": ["unavailable_output"],
        "cypher_statement": state.get("cypher_statement"),
        "database_records": [''],
        'answer': "I couldn't find any relevant information in the database",
        "total_tokens": [-1],
        "prompt_tokens": [-1],
        "completion_tokens": [-1]
    }