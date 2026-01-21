from langgraph.graph import END, START, StateGraph
from Nodes.States.states import  OverallState,InputState,OutputState
from Configuration.configurations import ConfigSchema
from Nodes.schema_filtering import schema_filtering
from Nodes.cypher_generator import cypher_generator
from Nodes.cypher_executor import cypher_executor

import subprocess
import sys
sys.path.append('Nodes')

#Define the graph
workflow = StateGraph(OverallState, input=InputState, output=OutputState, config_schema=ConfigSchema)
#Add nodes
workflow.add_node(schema_filtering)
workflow.add_node(cypher_generator)
workflow.add_node(cypher_executor)
#Add edges
workflow.add_edge(START, "schema_filtering")
workflow.add_edge("schema_filtering", "cypher_generator")
workflow.add_edge("cypher_generator", "cypher_executor")    
workflow.add_edge("cypher_executor",  END)

app = workflow.compile()
# display(Image(app.get_graph().draw_mermaid_png(output_file_path="graph_tzo.png")))