from langgraph.graph import END, START, StateGraph
from IPython.display import Image, display
from Nodes.States.states import  OverallState,InputState,OutputState
from Configuration.configurations import ConfigSchema
from Nodes.cypher_generator import cypher_generator
from Nodes.cypher_evaluator import cypher_evaluator
from Nodes.cypher_corrector import cypher_corrector
from Nodes.cypher_executor import cypher_executor
from Nodes.output_generator import output_generator
from Nodes.unavailable_output import unavailable_output
from Edges.conditional_edges import validate_cypher_condition

import subprocess
import sys
sys.path.append('Nodes')

def get_gpu_memory_in_gb():
    result  = subprocess.run(['nvidia-smi', 
                             '--query-gpu=memory.total,memory.used,memory.free', 
                             '--format=csv,noheader,nounits'],
                            stdout=subprocess.PIPE, text=True)
    memory_info = result.stdout.strip().split('\n')
    for i, gpu in enumerate(memory_info):
        total, used, free = map(int, gpu.split(','))
        print(f"GPU {i}: Total: {total / 1024:.2f} GB, Used: {used / 1024:.2f} GB, Free: {free / 1024:.2f} GB")


#Define the graph
workflow = StateGraph(OverallState, input=InputState, output=OutputState,config_schema=ConfigSchema)
#Add nodes
workflow.add_node(cypher_generator)
workflow.add_node(cypher_evaluator)
workflow.add_node(cypher_corrector)
workflow.add_node(cypher_executor)
workflow.add_node(output_generator)
workflow.add_node(unavailable_output)
#Add edges
workflow.add_edge(START, "cypher_generator")
workflow.add_edge("cypher_generator", "cypher_evaluator")
workflow.add_conditional_edges("cypher_evaluator", validate_cypher_condition)
workflow.add_edge("cypher_corrector", "cypher_evaluator")
workflow.add_edge("cypher_executor", "output_generator")    
workflow.add_edge("output_generator",  END)
workflow.add_edge("unavailable_output",  END)


app = workflow.compile()
# display(Image(app.get_graph().draw_mermaid_png(output_file_path="langgraph_QA_chain.png")))