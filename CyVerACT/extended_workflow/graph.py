from langgraph.graph import END, START, StateGraph
from Nodes.States.states import  OverallState,InputState,OutputState
from Configuration.configurations import ConfigSchema
from Nodes.schema_retriever import schema_retriever
from Nodes.schema_filtering import schema_filtering
from Nodes.cypher_generator import cypher_generator
from Nodes.cyver_evaluator import cyver_evaluator
# from Nodes.cypher_evaluator import cypher_evaluator
from Nodes.unavailable_output import unavailable_output
from Nodes.cypher_corrector import cypher_corrector
from Nodes.cypher_executor import cypher_executor
from Nodes.output_generator import output_generator
from Edges.conditional_edges_extended import select_next_action

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
workflow.add_node(schema_filtering)
workflow.add_node(schema_retriever)
workflow.add_node(cypher_generator)
workflow.add_node(cyver_evaluator)
workflow.add_node(cypher_corrector)
workflow.add_node(cypher_executor)
workflow.add_node(output_generator)
workflow.add_node(unavailable_output)
#Add edges
workflow.add_edge(START, "schema_filtering")
workflow.add_edge("schema_filtering", "cypher_generator")
workflow.add_edge("schema_retriever", "cypher_generator")
workflow.add_edge("cypher_generator", "cyver_evaluator")
workflow.add_conditional_edges("cyver_evaluator", select_next_action)
workflow.add_edge("cypher_corrector", "cyver_evaluator")
workflow.add_edge("cypher_executor", "output_generator")    
workflow.add_edge("output_generator",  END)
workflow.add_edge("unavailable_output",  END)


app = workflow.compile()
# display(Image(app.get_graph().draw_mermaid_png(output_file_path="graph_tzo.png")))