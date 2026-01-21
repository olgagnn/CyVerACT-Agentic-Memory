import os
from dotenv import load_dotenv
from typing import Annotated, TypedDict, List
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from neo4j import GraphDatabase
from CyVer import SyntaxValidator, SchemaValidator, PropertiesValidator # imported CyVer here!  

# --- Import CyVer (Προσάρμοσε το ανάλογα με το πώς εγκαταστάθηκε) ---
try:
    from CyVer.validators import SyntaxValidator, SchemaValidator, PropertyValidator
    CYVER_AVAILABLE = True
except ImportError:
    print("⚠️ CyVer not found or import path differs. Running without validation for now.")
    CYVER_AVAILABLE = False

# 1. Setup Environment
load_dotenv()

# Setup Neo4j
driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
)

# Setup LLM
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

# 2. Define State (Η Μνήμη της συνομιλίας)
class AgentState(TypedDict):
    messages: List[BaseMessage]   # Episodic Memory (Chat History)
    cypher_query: str             # Το query που έγραψε
    query_results: List[dict]     # Τα αποτελέσματα από τη βάση
    error: str | None             # Αν υπάρχει λάθος
    iterations: int               # Μετρητής προσπαθειών

# 3. Define Nodes (Τα βήματα του Agent)

def generate_cypher(state: AgentState):
    """Bήμα 1: Το LLM γράφει Cypher query"""
    print("\n--- 🧠 THINKING (Generating Cypher) ---")
    messages = state['messages']
    error = state.get('error')
    
    # Schema της Movies DB (Hardcoded για αρχή - αργότερα θα το τραβάμε δυναμικά)
    schema = "Nodes: Movie {title, released, tagline}, Person {name, born}. Rel: (:Person)-[:ACTED_IN]->(:Movie), (:Person)-[:DIRECTED]->(:Movie)"
    
    system_msg = f"""You are a Neo4j Expert using the Movies database.
    Schema: {schema}
    Task: Convert the user's question into a Cypher query.
    IMPORTANT: Return ONLY the Cypher code. No markdown (```), no explanations."""
    
    # Αν υπήρχε λάθος πριν, το προσθέτουμε στο context (Self-Correction)
    if error:
        messages.append(HumanMessage(content=f"Your previous query had an error: {error}. Please fix it."))
        
    messages = [SystemMessage(content=system_msg)] + messages
    response = llm.invoke(messages)
    
    # Καθαρισμός του αποτελέσματος από markdown αν υπάρχει
    clean_query = response.content.replace("```cypher", "").replace("```", "").strip()
    
    return {"cypher_query": clean_query, "iterations": state.get("iterations", 0) + 1}

def validate_cypher(state: AgentState):
    """Βήμα 2: Έλεγχος με CyVer"""
    print("\n--- 🛡️ VALIDATING (CyVer Check) ---")
    query = state['cypher_query']
    
    if not CYVER_AVAILABLE:
        return {"error": None} # Αν δεν έχουμε CyVer, περνάμε ελεύθερα (για δοκιμή)

    # Εδώ καλούμε τους validators του CyVer
    # (Προσαρμογή ανάλογα με το API του CyVer)
    try:
        # syntax_val = SyntaxValidator(driver)
        # if not syntax_val.validate(query):
        #     return {"error": "Syntax Error detected by CyVer"}
        pass 
    except Exception as e:
        print(f"Validation warning: {e}")

    return {"error": None} # Υποθέτουμε ότι είναι valid για τώρα

def execute_cypher(state: AgentState):
    """Βήμα 3: Εκτέλεση στη Neo4j"""
    print("\n--- ⚡ EXECUTING ---")
    query = state['cypher_query']
    
    try:
        # Προσθέτουμε το database_="movies" για να ξέρει πού να ψάξει
        results = driver.execute_query(query, database_="movies")[0]
        data = [r.data() for r in results]
        return {"query_results": data, "error": None}
    except Exception as e:
        return {"error": str(e)} # Αν σκάσει η βάση, επιστρέφουμε το λάθος

def generate_answer(state: AgentState):
    """Βήμα 4: Τελική Απάντηση"""
    print("\n--- 🗣️ ANSWERING ---")
    results = state['query_results']
    user_q = state['messages'][-1].content
    
    prompt = f"""User asked: {user_q}
    Database found: {results}
    Answer the user politely based on the data."""
    
    response = llm.invoke(prompt)
    return {"messages": [response]} # Προσθήκη απάντησης στο ιστορικό

# 4. Build the Graph (Η Ροή)
workflow = StateGraph(AgentState)

workflow.add_node("generate_cypher", generate_cypher)
workflow.add_node("validate_cypher", validate_cypher)
workflow.add_node("execute_cypher", execute_cypher)
workflow.add_node("generate_answer", generate_answer)

workflow.add_edge(START, "generate_cypher")
workflow.add_edge("generate_cypher", "validate_cypher")

# Απόφαση: Αν είναι valid προχώρα, αλλιώς ξαναπροσπάθησε
def check_validation(state):
    if state.get("error"):
        if state["iterations"] > 3: # Max retries
            return "end_failure"
        return "retry"
    return "valid"

workflow.add_conditional_edges(
    "validate_cypher",
    check_validation,
    {
        "retry": "generate_cypher",
        "valid": "execute_cypher",
        "end_failure": END
    }
)

def check_execution(state):
    if state.get("error"):
        return "retry" # Αν σκάσει η Neo4j, ξαναδοκίμασε να γράψεις άλλο query
    return "success"

workflow.add_conditional_edges(
    "execute_cypher",
    check_execution,
    {
        "retry": "generate_cypher",
        "success": "generate_answer"
    }
)

workflow.add_edge("generate_answer", END)

# Memory Checkpointer (Για να θυμάται τη συζήτηση!)
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)

# 5. Run it!
if __name__ == "__main__":
    thread_id = {"configurable": {"thread_id": "1"}}
    
    print("🤖 Agent is ready! (Type 'quit' to exit)")
    while True:
        user_input = input("User: ")
        if user_input.lower() in ["quit", "exit"]:
            break
            
        # Τρέξιμο του Agent
        for event in app.stream({"messages": [HumanMessage(content=user_input)], "iterations": 0}, config=thread_id):
            pass # Αφήνουμε τα prints μέσα στα functions να δείξουν τι γίνεται
            
        # Εμφάνιση της τελικής απάντησης
        final_state = app.get_state(thread_id)
        if final_state.values.get("messages"):
            print(f"AI: {final_state.values['messages'][-1].content}")