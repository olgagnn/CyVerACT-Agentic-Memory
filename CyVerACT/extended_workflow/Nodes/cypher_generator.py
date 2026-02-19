from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.config import RunnableConfig
from huggingface_hub import InferenceClient
from langchain_community.callbacks import get_openai_callback


from Nodes.States.states import  OverallState
# from Configuration.models import models

# Importing HYBRID MEMORY
try:
    from Memory.hybrid_manager import HybridMemoryManager
    # Initialize HYBRID MEMORY HERE !!!
    hybrid_memory = HybridMemoryManager()
    memory_available = True
    print("[Cypher Generator] Hybrid Memory Loaded")
except ImportError:
    print("WARNING: HybridMemoryManager not found. Proceeding without memory.")
    memory_available = False

system_prompt = """
                Task: Generate Cypher statement to query a graph database. 
                Instructions: Use only the provided relationship types and properties in the schema.
                Do not use any other relationship types or properties that are not provided in the schema.
                Do not include any explanations or apologies in your responses.
                Do not respond to any questions that might ask anything else than for you to construct a Cypher statement.
                Do not include any text except the generated Cypher statement.
                """
# Adding memory context here :)
human_prompt =  """
                Generate Cypher statement to query a graph database, as plain text without any code block formatting or backticks.
                Use only the provided relationship types and properties in the schema. 
                Instructions:
                If memory_context contains previous mistakes for this question, avoid making the same mistake again.
                Do not repeat previously known invalid Cypher statements.
                Respond with the corrected or new Cypher statement only.
                \nSchema: {schema}
                \n{memory_context}
                \nQuestion: {question}
                \nCypher statement:
                
                """
text2cypher_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                system_prompt
            ),
        ),
        (   #as plain text without any code block formatting or backticks : ADDED
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
        #         system_prompt
        #     ),
        # ),
        (   #as plain text without any code block formatting or backticks : ADDED
            "human",
            (
              system_prompt + human_prompt
            ),
        ),
    ]
)

## Create the node for the Cypher generator
def cypher_generator(state: OverallState, config:RunnableConfig) -> OverallState:
    """
    Generates a cypher statement based on the provided schema and user input
    Added Hybrid Memory!
    """
    model_name = config['configurable']['model_name']
    schema = state.get("schema")
    question = state.get("question")

    chat_model = config['configurable']['model']

    # Hybrid Memory Retrieval here !!! 
    memory_context = ""
    if memory_available:
        try:
            
            # ONLY SEARCH PAST MISTAKES, NO ADD/LEARN
            past_lessons = hybrid_memory.get_procedural_lessons(question)
            
            if past_lessons:
                print(f"[Memory] Found past mistakes for similar queries!" + past_lessons)
                memory_context = f"\nPrevious Mistakes & Lessons:\n{past_lessons}\n"
            else:
                print("[Memory] No relevant past mistakes found.")
                
        except Exception as e:
            print(f"[Memory] Retrieval Error: {e}")


    if model_name == 'gemma2_9b' or model_name == 'finetuned_gemma2_9b' or model_name =='finetuned_gemma2_9b_local':
        text2cypher_chain = text2cypher_prompt_flattened | chat_model | StrOutputParser()
    else:    
        text2cypher_chain = text2cypher_prompt | chat_model | StrOutputParser()

    with get_openai_callback() as cb:
        generated_cypher = text2cypher_chain.invoke({
            "question": question,
            "schema": schema,
            "memory_context": memory_context # for the prompt above
        })

    total_tokens = cb.total_tokens
    prompt_tokens = cb.prompt_tokens
    completion_tokens = cb.completion_tokens

    if model_name == 'llama3_2_3b_local':
        generated_cypher = generated_cypher.split('assistant<|end_header_id|>')[1].strip()
    elif model_name == 'finetuned_gemma2_9b_local':
        generated_cypher = generated_cypher.split('<start_of_turn>model\n')[1].strip()

    print('Cypher Generator: START')
    # print('The selected model is', model_name)
    # print('Generated Cypher statement: \n {}'.format(generated_cypher))
    # print('Cypher Generator: END')
    # print()

    # !!!! TESTING WRONG QUERIES TO CHECK COGNEE PROCEDURAL
    fake_cypher = "MATCH (p:Person)-[:ACTED_IN]->(f:Film) RETURN p.name, f.title"
    
    return {"cypher_statement": fake_cypher, 
            "path": ["cypher_generator"],
            "total_tokens": [total_tokens],
            "prompt_tokens": [prompt_tokens],
            "completion_tokens": [completion_tokens]
            }