from Nodes.States.states import  OverallState
from typing import Literal

def validate_cypher_condition(state: OverallState,) -> Literal[ "cypher_corrector", "cypher_executor"]: #"generate_final_answer",
    if state.get("next_action") == "cypher_executor":
        return "cypher_executor"
    elif state.get("next_action") == "cypher_corrector":
        return "cypher_corrector"