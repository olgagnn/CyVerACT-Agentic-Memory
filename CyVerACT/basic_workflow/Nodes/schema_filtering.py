from neo4j import GraphDatabase,basic_auth
from neo4j_graphrag.schema import get_structured_schema
from nltk.stem import PorterStemmer
from sentence_transformers import SentenceTransformer,util
import torch
import os 

from Nodes.States.states import InputState, OverallState
import sys
# This adds the parent directory (../) to the list of directories Python will search for modules.
# The ../ refers to the directory one level up from the current working directory.
sys.path.append('../')
from utils.KG_schema_formatting import format_final_schema,get_structured_schema_custom
from utils.nlp_functions import preprocess_text,split_camel_case,split_by_underscore
from utils.access_precomputed import get_kg_schema, save_kg_schema

KG_structured_schema_json_path = os.path.abspath(os.path.join("..", "precomputed", "KG_schemas", "kg_structured_schema.json"))


#Define model for word semantic similarity
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
device = 'cuda' if torch.cuda.is_available() else 'cpu'
model = model.to(device)
    
def match_with_search_terms(search_terms: list[str], natural_language_question_term: str, match_substrings: bool = False) -> bool:
    """
    Checks if the single preprocessed word from the natural language question matches any of the search terms.
    
    - If `match_substrings` is True, it checks if any search term is a substring of the question term.
    - Otherwise, it checks for exact matches.
    """
    if match_substrings:
        #if the natural language question term is a substring of any search term ir vice versa return True
        return any(natural_language_question_term in term  for term in search_terms) or \
               any(term in natural_language_question_term for term in search_terms)
    else:
        #Check for exact match withot stemming
        exact_match = any(natural_language_question_term == term  for term in search_terms)
        if not exact_match:#Check for exact match with stemming
            stemmer = PorterStemmer()
            stemmed_question_term = stemmer.stem(natural_language_question_term)
            stemmed_search_terms = [stemmer.stem(term) for term in search_terms]
            exact_match =any(stemmed_question_term == term for term in stemmed_search_terms)
            # if exact_match:
            #     print(f'Match found with stemming {natural_language_question_term} -> {stemmed_question_term} with {stemmed_search_terms}')
        return exact_match
        # return natural_language_question_term in search_terms

def batch_encode_terms(model, terms: list[str], device):
    '''
    Encode a list of terms into embeddings using the sentence transformer model
    Returns a dict with terms as keys and their embeddings as values
    '''
    embeddings = model.encode(terms, convert_to_tensor=True, device=device)
    return dict(zip(terms, embeddings))

def high_semantic_similarity(search_terms: list[str], natural_language_question_term: str, embeddings,embeddings_keys):
    ''' 
    Check if the question term is semantically similar to any of the search terms using cosine similarity
    Returns True if any term has a cosine similarity >= 0.7 with the question term
    '''
    filtered_terms = [t for t in search_terms if t in embeddings_keys]

    if natural_language_question_term not in embeddings_keys or not filtered_terms:
        return False

    return any(
        round(util.cos_sim(embeddings[natural_language_question_term], embeddings[t]).item(),2) >= 0.7
        for t in filtered_terms
    )

def update_filtered_schema_with_nodes_rels(pruned_structure_dict,type_name, label, property_dict_list, one_hop_paths_list):
    ''' 
    It adds to the filtered KG schema the node label or rel type with its properties 
    and the one hop path, if any, that this node label or rel type is part of.
    Note: it checks only rels that have properties

    pruned_structure_dict: dict the dictionary from which we will construct the filtered schema
    type_name: str ('node_props','rel_props') defines if the label added will be node or rel
    label: str the node label or rel type to be added to the filtered schema
    property_dict_list: list of the properties of the input label (node label or rel type) 
    one_hop_paths_list: list of all the one hop paths of the KG schema
    
    It returns the updated pruned_structure_dict and the updated one_hop_paths_list.
    '''
    if label not in pruned_structure_dict[type_name]:
        pruned_structure_dict[type_name][label] = property_dict_list #add the label or rel type to the filtered schema with their properties
        #add the one hop paths they may be part of, and remove them form the list of one hop paths
        for relationship in one_hop_paths_list[:]:    
            if relationship['start'] == label or relationship['end'] == label or relationship['type'] == label:   
                #add the one-hop path to the filtered schema            
                pruned_structure_dict['relationships'].append({'start':relationship['start'], 'type':relationship['type'], 'end':relationship['end']})
                #remove this onehop path so i dont double check it in a next iteration
                one_hop_paths_list.remove(relationship)
                # # add the nodes or rel that belog to the added one hop path
                # for node_label in [relationship['start'],  relationship['end']]:
                #     if (node_label not in pruned_structure_dict['node_props']) and (node_label in structured_schema['node_props']):
                #         pruned_structure_dict['node_props'][node_label] = structured_schema['node_props'][node_label] #add the label (if it haas properties) to the filtered schema with their properties
                # rel_type = relationship['type']
                # if (rel_type not in pruned_structure_dict['rel_props']) and (rel_type in structured_schema['rel_props']):
                #     pruned_structure_dict['rel_props'][rel_type] = structured_schema['rel_props'][rel_type] #add the rel type (If it has properties) to the filtered schema with their properties


    return pruned_structure_dict, one_hop_paths_list

def update_filtered_schema_with_one_hop_paths(pruned_structure_dict,type_name, relationship):
    ''' 
    It adds to the filtered KG schema the one hop paths that their rel type was found in the schema.

    pruned_structure_dict: dict the dictionary from which we will construct the filtered schema
    type_name: str ('relationships') Defines that one-hop-paths will be added to the filtered schema
    relationship: dict the relationship (one-hop-path) to be added to the filtered schema
   
    It returns the updated pruned_structure_dict and the updated one_hop_paths_list.
    '''
    
    pruned_structure_dict[type_name].append({'start':relationship['start'], 'type':relationship['type'], 'end':relationship['end']})
    # #Check the node labels of the one hop path to be added
    # for node_label in [relationship['start'],  relationship['end']]:
    #     if (node_label not in pruned_structure_dict['node_props']) and (node_label in structured_schema['node_props']):
    #         pruned_structure_dict['node_props'][node_label] = structured_schema['node_props'][node_label] #add the label (if it haas properties) to the filtered schema with their properties
    return pruned_structure_dict

def get_filtered_schema_by_question(driver, database_name, natural_language_question,
                                          match_substrings=False,
                                          check_semantic_similarity=False,
                                          inline_props=True):
    '''
    It returns a filtered schema of the KG based on the natural language question.
    The filtering is done by checking if the node labels or rel types are present in the question.
    If a node label or rel type is found in the question, then they are added with their properties to the filtered schema.
    Also the one hop paths the may be part of are added to the schema.
    If a rel type of a one hop path is found in the question (that was not found by checking rel types if they had no properties), the one hop path is added to the filtered schema.
    
    It searches for each term in the natural language question if they match exactly or semantically with one or more node labels, rel types or one hop paths rels.
    
    driver: the neo4j driver of the KG database
    database_name(str): the database name
    natural_language_question: str the natural language question to be used for filtering
    structured_schema: dict the structured schema of the KG
    match_substrings: bool if True, it matches substrings in the question (default is False)
    semantic_similarity: bool if True, it uses semantic similarity to match words in the question (default is False)
    inline_props : bool If True, includes property types inline within one-hop path descriptions in the returned filtered schema. 
                             If False, lists the node/rel definitions separately.
    
    It returns the filtered schema of the KG.
    '''
    # Initialize an empty dictionary to store the filtered schema
    pruned_structure_dict = {
        'node_props': {},
        'rel_props': {},
        'relationships': []
    }

    # Get the full structured schema from the database
    # Try to load the KG schema for the given database_name from  kg_structured_schema.json
    structured_schema = get_kg_schema(database_name, KG_structured_schema_json_path)
    if not structured_schema:
        # structured_schema = get_structured_schema(driver, is_enhanced = False, database = database_name, sanitize = False)
        structured_schema= get_structured_schema_custom(driver, is_enhanced = False, database = database_name, sanitize = False)
        save_kg_schema(database_name, structured_schema, KG_structured_schema_json_path)
       
    
    one_hop_paths_list = structured_schema['relationships'].copy()

     # The question is preprocessed to remove special characters, 
     # convert to lowercase and remove stopwords and split into words
    natural_language_question_terms = list(set(preprocess_text(natural_language_question).split()))
    natural_language_question_terms_lower = [t.lower() for t in natural_language_question_terms]

    # Collect all terms from the schema to embed
    all_kg_terms = set()

    # Nodes and Relationships
    for type_name in ['node_props', 'rel_props']:
        for label in structured_schema[type_name].keys():
            splits = split_camel_case(label)
             #add the original label in search terms if it was split
            if len(splits) > 1:
                all_kg_terms.update(s.lower() for s in (splits + [label]))
            else:
                all_kg_terms.add(label.lower())

    # One Hop Paths
    for rel in one_hop_paths_list:
        splits = split_by_underscore(rel['type'])
         #add the original label in search terms if it was split
        if len(splits) > 1:
            all_kg_terms.update(s.lower() for s in (splits + [rel['type']]))
        else:
            all_kg_terms.add(rel['type'].lower())

    # Include question terms to ensure they’re also embedded
    all_terms_to_encode = list(all_kg_terms.union(natural_language_question_terms_lower))

    # Batch encode all required terms once
    embeddings = batch_encode_terms(model, all_terms_to_encode, device)

    embeddings_keys = set(embeddings.keys())  # For quick lookup
    # Cache semantic match results to avoid recomputation
    semantic_match_cache = {}  

    # Process each term in the question
    for term, term_lower in zip(natural_language_question_terms, natural_language_question_terms_lower):
        # print(f"Checking term: {term } (lower: {term_lower})")

        # Check against node and relationship properties
        for type_name in ['node_props', 'rel_props']:
            for label, property_dict_list in structured_schema[type_name].items():
                split_labels = split_camel_case(label)
                search_terms = split_labels + [label] if len(split_labels) > 1 else [label]
                search_terms_lower = [s.lower() for s in search_terms]
                # Try exact or substring match
                if match_with_search_terms(search_terms_lower, term_lower, match_substrings=match_substrings):
                    # print(f"Found exact label: {label} in question with search term {search_terms_lower}")
                    pruned_structure_dict, one_hop_paths_list = update_filtered_schema_with_nodes_rels(
                        pruned_structure_dict, type_name, label, property_dict_list, one_hop_paths_list)

                # Elif not exact match, check for high semantic similarity match(if True)
                elif check_semantic_similarity:
                    key = (tuple(search_terms_lower), term_lower)
                    if key not in semantic_match_cache:
                        semantic_match_cache[key] = high_semantic_similarity(search_terms_lower, term_lower, embeddings,embeddings_keys)
                    if semantic_match_cache[key]:
                        # print(f"Found by semantic similarity: {label} in question with search term {search_terms_lower}")
                        pruned_structure_dict, one_hop_paths_list = update_filtered_schema_with_nodes_rels(
                            pruned_structure_dict, type_name, label, property_dict_list, one_hop_paths_list)

        # Now check relationships (one-hop paths)
        type_name = 'relationships'
        for relationship in one_hop_paths_list[:]:  # Copy for safe removal
            split_terms = split_by_underscore(relationship['type'])
            search_terms = split_terms + [relationship['type']] if len(split_terms) > 1 else [relationship['type']]
            search_terms_lower = [s.lower() for s in search_terms]


            # Try exact or substring match
            if match_with_search_terms(search_terms_lower, term_lower, match_substrings=match_substrings):
                # print(f"Found relationship: {relationship['type']} from one hop path {relationship} in question with search term {search_terms_lower}")
                pruned_structure_dict = update_filtered_schema_with_one_hop_paths(pruned_structure_dict, type_name, relationship)

            # Elif not exact match, check for high semantic similarity match(if True)
            elif check_semantic_similarity:
                key = (tuple(search_terms_lower), term_lower)
                if key not in semantic_match_cache:
                    semantic_match_cache[key] = high_semantic_similarity(search_terms_lower, term_lower, embeddings,embeddings_keys)
                if semantic_match_cache[key]:
                    # print(f"Found by semantic similarity: {relationship['type']} in question with search term {search_terms_lower}")
                    pruned_structure_dict = update_filtered_schema_with_one_hop_paths(pruned_structure_dict, type_name, relationship)

    # Format and return the final filtered schema
    filtered_schema = format_final_schema(driver, database_name, pruned_structure_dict, structured_schema, inline_props=inline_props)
    return filtered_schema

#----------Define the node------------------
def schema_filtering(state: InputState) -> OverallState:
    """
    Gets the schema from the database and filters it based on the
    natural language question. 
    """

    question = state.get("question")
    database_url = state.get("database_url")
    database_name = state.get("database_name")
    database_user = state.get("database_user")
    database_password = state.get("database_password")

    #Connect to the database
    driver = GraphDatabase.driver(database_url, auth=basic_auth(database_user, database_password) )
    print('Schema filtering Agent: START')
    #Get filtered schema based on question
    filtered_schema = get_filtered_schema_by_question(driver, database_name, question, match_substrings = False, check_semantic_similarity = True, inline_props= True)

    # print('Schema filtering Agent: END ')
    # print()

    return {"schema": filtered_schema, 
            "neo4j_driver":driver,
            "path": ["schema_filtering"],
            "total_tokens": [-1],
            "prompt_tokens": [-1],
            "completion_tokens": [-1]}