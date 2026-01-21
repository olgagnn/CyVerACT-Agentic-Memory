from typing import Set, Any, Dict, List, Tuple, Hashable
from utils.Evaluation.cypher_metrics import jaccard_formula
from neo4j.graph import Node,Relationship



def floatify(v: Any) -> Any:
    """
    Attempts to convert a value to a float if it is a string and represents a
    number, or recursively apply the conversion to elements within a list or dict.
    """
    # Case 1: Check if `v` is a string
    if isinstance(v, str):
        return v # Returns `v` unchanged if it's a string
    # Case 2: Try to directly convert `v` to a float
    try:
        f = float(v) # If successful, this returns `v` as a float
        return f
    except:
        pass
    # Case 3: If `v` is a list, recursively apply `floatify` to each element
    if isinstance(v, list):
        return [floatify(x) for x in v]
    # Case 4: If `v` is a dict, recursively apply `floatify` to each value
    if isinstance(v, dict):
        return {k: floatify(u) for k, u in v.items()}
    # Case 5: Return `v` unchanged if it is neither a string, float-compatible, list, nor dict
    return v

def make_hashable(v: Any) -> Hashable:
    """
    Convert a value to a hashable type (needed for set operations).
    """

    # Step 1: Attempt to convert the input value `v` to a float-compatible version
    float_v = floatify(v)
    # Step 2: Check if `float_v` is hashable
    if not isinstance(float_v, Hashable):
        # If not hashable, convert it to a string (strings are hashable)
        return str(float_v)
    else:
        # If already hashable, return `float_v` as-is
        return float_v

def make_alignment(dictL: List[Dict], dictR: List[Dict]) -> Tuple[List[Set], List[Set]]:
    """
    Align rows from two lists of dictionaries based on their similarity.
    
    Parameters:
    dictL : List[Dict] - First list of dictionaries to align.
    dictR : List[Dict] - Second list of dictionaries to align.
    
    Returns:
    Tuple[List[Set], List[Set]] - Two lists of sets where each set represents a dictionary
    from the original lists, aligned based on similarity.
    """
    # Determine which list is smaller; if `dictL` is larger, set `swap` to True.
    swap = len(dictL) > len(dictR)

    # Step 1: Convert each dictionary in dictL and dictR to a set of hashable values.
    # Each set will represent a row for alignment purposes.
    setViewsL = [{make_hashable(v) for k, v in row.items()} for row in dictL]
    setViewsR = [{make_hashable(v) for k, v in row.items()} for row in dictR]
    # Swap the lists if dictL is larger than dictR to ensure setViewsL is the smaller list.
    if swap:
        setViewsL, setViewsR = setViewsR, setViewsL
    # Step 2: Align rows from setViewsL to setViewsR based on maximum similarity.
    # For each row in setViewsL:
    for i in range(len(setViewsL)):
        max_sim = -1 # Initialize max similarity to a low value.
        max_j = -1 # Initialize max index to -1 to indicate no match yet.
        # Compare the row with each row in setViewsR from index i onward.

        for j in range(i, len(setViewsR)):
            sim = jaccard_formula(setViewsL[i], setViewsR[j]) # Calculate jaccard similarity between sets.
            # If similarity is higher than max_sim, update max_sim and max_j to store best match.
            if sim > max_sim:
                max_j = j
                max_sim = sim
        
        # Step 3: Swap the best-matched row in setViewsR (at max_j) to position i.
        tmp = setViewsR[i]
        setViewsR[i] = setViewsR[max_j]
        setViewsR[max_j] = tmp
        # print(setViewsR)
    # Step 4: If `swap` was True, swap the results back to the original lists' order.
    if swap:
        setViewsL, setViewsR = setViewsR, setViewsL
    return setViewsL, setViewsR

def similarity(original_output: List[Dict], generated_output: List[Dict], list_view: bool) -> float:
    """
    Calculate the data frame similarity based on either the original row order or an alignment.
    
    Parameters:
    dictL : List[Dict] - First list of dictionaries representing the first data frame.
    dictR : List[Dict] - Second list of dictionaries representing the second data frame.
    list_view : bool - If True, use the original order of rows; otherwise, align the rows first.

    Returns:
    float - Jaccard similarity score between the two data frames.
    """
    dictL = original_output
    dictR = generated_output
    if list_view:
        # Step 1: Use the original row order for lists of dictionaries.
        # Create views that extract values from each row in dictL and dictR.
        view_L = [row.values() for row in dictL]
        view_R = [row.values() for row in dictR]
    else:
        # Step 2: If not using list view, align the rows based on similarity.
        view_L, view_R = make_alignment(dictL, dictR) # Get aligned rows.

    # Step 3: Create sets for the elements with their corresponding row indices.
    totalSetL = set() # Set to hold (index, hashable_value) for dictL
    for i, s in enumerate(view_L): # Iterate through each row in view_L
        for elem in s: # Iterate through each element in the row
            totalSetL.add((i, make_hashable(elem))) # Add (row index, hashable element) to totalSetL
    totalSetR = set() # Set to hold (index, hashable_value) for dictR
    for i, s in enumerate(view_R): # Iterate through each row in view_R
        for elem in s: # Iterate through each element in the row
            totalSetR.add((i, make_hashable(elem))) # Add (row index, hashable element) to totalSetR
    # Step 4: Calculate intersection and union of the two sets.
    intersection = totalSetL.intersection(totalSetR)
    union = totalSetL.union(totalSetR)
    if len(union) == 0 and len(intersection) == 0:
        return 1.0 # If both sets are empty, return maximum similarity
    elif len(union) == 0:
        return 0.0 # If union is empty, return minimum similarity.

    return len(intersection) / len(union)

##################################################
########### Jaccard similarity output ############
##################################################

def execute_query(driver, query, database_name):
        with driver.session(database=database_name) as session:
            return [dict(result) for result in session.run(query)] 

def extract_properties(record):
    """
    If a query returns in its record nodes or relationships (and not specific properties), extract from the nodes and rels
    theri properties to be used as output
    """
    for key, value in record.items():
        if isinstance(value, Node) or isinstance(value, Relationship):
            return dict(value)
        else:
            return record
            
def jaccard_similarity_output(driver, original, generated,database_name):
    """
    Compute the Jaccard similarity of two data frames (lists of dictionaries),
    taking into account the order of rows if indicated by the involved Cypher queries.
    """
    try:
        original_output = execute_query(driver, original, database_name)
        generated_output = execute_query(driver, generated, database_name)

        # If the output are whole nodes or relationships, extract the properties to compare the similarity
        original_properties = [extract_properties(record) for record in original_output]
        generated_properties = [extract_properties(record) for record in generated_output]

        return similarity(original_properties, generated_properties, "order by" in f"{original}".lower())
    
    except Exception as e:
        
        return 0.0 # return minimum similarity.

##################################################
############### Pass@1 output ####################
##################################################

# def pass_1_output(pair_L, pair_R):
#     """
#     Compute the pass@1 of two data frames (lists of dictionaries),
#     taking into account the order of rows if indicated by the involved Cypher queries.
#     """
#     cypher_L, dict_L = pair_L
#     cypher_R, dict_R = pair_R

#     if similarity(dict_L, dict_R, "order by" in f"{cypher_L}".lower()) == 1: 
#         pass_1 =True
#     else: 
#         pass_1 =False

#     return pass_1


def pass_1_output(driver, original, generated, database_name):
    """
    Compute the pass@1 of two data frames (lists of dictionaries),
    taking into account the order of rows if indicated by the involved Cypher queries.
    """
    try: 
        original_output = execute_query(driver, original, database_name)
        generated_output = execute_query(driver, generated, database_name)

        # If the output are whole nodes or relationships, extract the properties to compare the similarity
        original_properties = [extract_properties(record) for record in original_output]
        generated_properties = [extract_properties(record) for record in generated_output]

        if similarity(original_properties, generated_properties, "order by" in f"{original}".lower()) == 1: 
            pass_1 =True
        else: 
            pass_1 = False
        return pass_1
    except Exception as e:
        pass_1 = False
        return pass_1