from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.config import RunnableConfig
from Nodes.States.states import  OverallState
from langchain_neo4j import Neo4jGraph
from langchain_community.callbacks import get_openai_callback

# Importing Memory Manager
try:
    from memory.manager import MemoryManager
    memory_available = True
except ImportError:
    print("WARNING: MemoryManager not found. Proceeding without memory.")
    memory_available = False

system_prompt = """
    Given an input question, convert it to a Cypher query. No pre-amble.
    Do not wrap the response in any backticks or anything else. Respond with a Cypher statement only!
"""
# Adding memory context here :)
human_prompt = """
    You are a Neo4j expert. Given an input question, create a syntactically correct Cypher query to run.
    Do not wrap the response in any backticks or anything else. Respond with a Cypher statement only!
    Here is the schema information
    {schema}

    {memory_context}

    User input: {question}
    Cypher query:
"""
text2cypher_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
              system_prompt
            ),
        ),
        (
            "human",
            (
                human_prompt
            ),
        ),
    ]
)

text2cypher_prompt_flattened = ChatPromptTemplate.from_messages(
    [
        # (
        #     "system",
        #     (
        #       system_prompt
        #     ),
        # ),
        (
            "human",
            (
                system_prompt + human_prompt
            ),
        ),
    ]
)




def cypher_generator(state: OverallState, config:RunnableConfig) -> OverallState:
    """
    Generates a cypher statement based on the provided schema and user input
    """
    print('--------------------------------------------------Cypher Generator: START')
    model_name = config['configurable']['model_name']
    question = state.get("question")
    database_url = state.get("database_url")
    database_name = state.get("database_name")
    database_user = state.get("database_user")
    database_password = state.get("database_password")

    enhanced_graph = Neo4jGraph(url=database_url, username = database_user,
                                password =  database_password, database = database_name,
                                enhanced_schema=True)
    schema = enhanced_graph.schema
    # print('Database Schema:',schema)

    # Memory Retrieval here !!! 
    memory_context = ""
    if memory_available:
        try:
            # Getting current memory provider  
            memory_store = MemoryManager.get_memory_provider()
            
            # Looking for stored errors/rules 
            past_rules = memory_store.get_relevant_rules(question)
            
            if past_rules:
                print(f"[Memory] Found relevant past errors/rules.")
                print(f"[DEBUG CONTENT]:\n{past_rules}") # DEBUGGING :(
                # Updating memory context for prompt 
                memory_context = f"\n### CRITICAL PAST MISTAKES TO AVOID \n{past_rules}\n"
            else:
                print("[Memory] No relevant past errors found.")
                
        except Exception as e:
            print(f"[Memory] Error retrieving from Zep: {e}")
            memory_context = ""

    chat_model = config['configurable']['model']

    
    if model_name == 'gemma2_9b' or model_name == 'finetuned_gemma2_9b' or model_name =='finetuned_gemma2_9b_local':
        text2cypher_chain = text2cypher_prompt_flattened | chat_model | StrOutputParser()
    else:    
        text2cypher_chain = text2cypher_prompt | chat_model | StrOutputParser()

    with get_openai_callback() as cb:
        # We need memory_context in chain invoke 
        generated_cypher = text2cypher_chain.invoke({
            "question": question,
            "schema": schema,
            "memory_context": memory_context 
        })

    total_tokens = cb.total_tokens
    prompt_tokens = cb.prompt_tokens
    completion_tokens = cb.completion_tokens

    # generated_cypher = text2cypher_chain.invoke(
    #     {
    #         "question": question,
    #         "schema": schema,
    #     }
    # )
    if model_name == 'llama3_2_3b_local':
        generated_cypher = generated_cypher.split('assistant<|end_header_id|>')[1].strip()
    elif model_name == 'finetuned_gemma2_9b_local':
        generated_cypher = generated_cypher.split('<start_of_turn>model\n')[1].strip()

    # --- TEST MODE: SABOTAGE (START) ---
    # If question involves 'Matrix', write the wrong relationship (ACTS_IN)
    # Goal: CyVer should fail in translating, Corrector should be called and write to memory 
    #if "Matrix" in question:
        #print("\n[TEST MODE] SABOTAGING ON PURPOSE WITH RELATIONSHIP (ACTS_IN)...")
        #generated_cypher = "MATCH (m:Movie {title: 'The Matrix'})<-[:ACTS_IN]-(p:Person) RETURN p"
    # --- TEST MODE: SABOTAGE (END) ---
    
    print(generated_cypher)
    print('-------------------------------Cypher Generator: END')
    
    return {"cypher_statement": generated_cypher, 
            "schema": schema,
            "path": ["cypher_generator"],
            "total_tokens": [total_tokens],
            "prompt_tokens": [prompt_tokens],
            "completion_tokens": [completion_tokens]}