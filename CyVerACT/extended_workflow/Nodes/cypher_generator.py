from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.config import RunnableConfig
from huggingface_hub import InferenceClient
from langchain_community.callbacks import get_openai_callback

from Nodes.States.states import  OverallState
# from Configuration.models import models

# MEMORY 
from Agent_Memory.memory_manager import MemoryManager

from Agent_Memory.memory_driver import get_memory_driver

from langchain_huggingface import HuggingFaceEmbeddings

# Initialize the embedder locally for memory lookups
embedder = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

system_prompt = """
                Task: Generate Cypher statement to query a graph database. 
                Instructions: Use only the provided relationship types and properties in the schema.
                Do not use any other relationship types or properties that are not provided in the schema.
                Do not include any explanations or apologies in your responses.
                Do not respond to any questions that might ask anything else than for you to construct a Cypher statement.
                Do not include any text except the generated Cypher statement.
                """
human_prompt =  """
                Generate Cypher statement to query a graph database,as plain text without any code block formatting or backticks.
                Use only the provided relationship types and properties in the schema.
                \nSchema: {schema}
                \n{episodic_memory}
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
    """
    model_name = config['configurable']['model_name']
    schema = state.get("schema")
    question = state.get("question")

    # ============================
    # MEMORY INIT & RETRIEVAL
    # ============================
    memory_driver = get_memory_driver()
    episodic_memory_str = ""
    try:
        memory_manager = MemoryManager(memory_driver)
        memory_manager.init_question(question)
        
        cached_cypher = memory_manager.check_episodic_memory(question, embedder)
        if cached_cypher:
            print(f"\n[EPISODIC MEMORY] Found a highly relevant past solution!")
            episodic_memory_str = (
                "\n=== PAST SUCCESSFUL EXPERIENCE ===\n"
                "You have solved a highly similar question before. "
                "Use the syntax and structure from this past successful Cypher query as a template:\n"
                f"{cached_cypher}\n"
                "==================================\n"
            )
    finally:
        memory_driver.close()

    chat_model = config['configurable']['model']

    if model_name == 'gemma2_9b' or model_name == 'finetuned_gemma2_9b' or model_name =='finetuned_gemma2_9b_local':
        text2cypher_chain = text2cypher_prompt_flattened | chat_model | StrOutputParser()
    else:    
        text2cypher_chain = text2cypher_prompt | chat_model | StrOutputParser()

    with get_openai_callback() as cb:
        generated_cypher = text2cypher_chain.invoke({
            "question": question,
            "schema": schema,
            "episodic_memory": episodic_memory_str
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
    
    return {"cypher_statement": generated_cypher, 
            "path": ["cypher_generator"],
            "total_tokens": [total_tokens],
            "prompt_tokens": [prompt_tokens],
            "completion_tokens": [completion_tokens],
            "cypher_history": [generated_cypher], # MEMORY
            }