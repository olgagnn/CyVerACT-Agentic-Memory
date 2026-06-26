from Nodes.States.states import  OverallState
from typing import Literal


def select_next_action(state: OverallState,) -> Literal[ "cypher_corrector", "cypher_executor",
                                                               'schema_retriever','unavailable_output']: #"generate_final_answer",
    if state.get("next_action") == "cypher_executor":
        return "cypher_executor"
    elif state.get("next_action") == "cypher_corrector":
        return "cypher_corrector"
    elif state.get("next_action") == 'unavailable_output':
        return 'unavailable_output'
    elif state.get("next_action") == 'schema_retriever':
        return 'schema_retriever'