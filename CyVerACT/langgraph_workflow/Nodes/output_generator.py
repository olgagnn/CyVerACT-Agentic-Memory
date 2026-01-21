''' Return the generated query'''
from Nodes.States.states import  OverallState, OutputState

def output_generator(state: OverallState) -> OutputState:
    """
    Returns the final query based on the user question and the retieved results.
    """
    print('----------------------------------------------Output Generator: START')
    # print('Output Generator: END')
    database_records = state.get("database_records")
    if database_records is not None:
        answer = "I found relevant information in the database"
        path_step = "output_generator"
    else:
        answer = "I couldn't find any relevant information in the database"
        path_step = "unavailable_output"
        database_records = ['']

    print(answer)    
    print(database_records)
    print('----------------------------------------------Output Generator: END')
    return {
        "path": [path_step],
        "cypher_statement": state.get("cypher_statement"),
        "database_records": database_records,
        "answer": answer  ,
        "total_tokens": [-1],
        "prompt_tokens": [-1],
        "completion_tokens": [-1]
    }