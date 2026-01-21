import regex as re
import neo4j
from functools import reduce
import pandas as pd

def identify_variables_and_construct_query(pattern, database_name):
    '''
    Identify node and relationship variables from a Cypher pattern and construct a dynamic query.
    '''
    node_var_pattern =  r"\((\w+)\)"
    rel_var_pattern =  r"\[(\w+)\]"
    
    # Identify node and relationship variables
    node_vars = re.findall(node_var_pattern, pattern)
    rel_vars = re.findall(rel_var_pattern, pattern)
    # If exist variables of nodes or rels
    if node_vars or rel_vars:
        # Match the pattern for extracting possible labels for nodes and relationships
        match_clause = f"MATCH {pattern}"
        
        # Dynamic WITH clause with LIMIT
        limit_clause = f"WITH {', '.join(node_vars+rel_vars)} LIMIT 100"

        # Prepare the WITH clause for nodes (extracting labels) and relationships (extracting types)
        with_clause = "WITH DISTINCT "
        
        # Collect node labels
        for node in node_vars:
            with_clause += f"labels({node}) AS {node}_labels, "
        # Collect relationship types
        for rel in rel_vars:
            with_clause += f"type({rel}) AS {rel}_type, "

        # Remove the trailing comma from the WITH clause
        with_clause = with_clause.rstrip(', ')
        
        # Create the UNWIND clause to unwind node labels and relationship types
        unwind_clause = ""
        for node in node_vars:
            unwind_clause += f"UNWIND {node}_labels AS {node}\n"
        
        for rel in rel_vars:
            unwind_clause += f"UNWIND [{rel}_type] AS {rel}\n"
        
        
        # Combine node_vars and rel_vars into a single list
        variables = [*node_vars, *rel_vars]

        # Construct the RETURN clause
        return_clause = "RETURN DISTINCT " + ", ".join(map(str, variables)).strip(', ')

        # Construct the full query
        if (database_name=='twitter'):
            query = match_clause + "\n" + limit_clause + "\n" + with_clause + "\n" + unwind_clause + "" + return_clause
        else:
            query = match_clause + "\n" + with_clause + "\n" + unwind_clause + "" + return_clause
        
        return query, node_vars, rel_vars
    
    else:
        return '',node_vars,rel_vars

def get_paths_after_inference(driver,all_paths_with_vars, database_name=None):
    ''' Gets as input a list with all the paths that have variables to be inferred.
    For each path we call the infer label that infers the combination of labels for all the variables in the path.
    The result is a dataframe with columns the variables and values the labels of each variable. Each row is a valid combination of labels.
    If the columns of dataframe (the variables of the path) are not mentioned again in any other dataframe from the other paths then i keep it as it is
    If at least one column of the dataframe matches the column of another dataframe then i join these 2 (so that ikeep only the valid combination of labels among all the variables)
    Finally return all the dataframes 
    
    Args:
        - driver: An instance of the Neo4j driver.
        - all_paths_with_vars (list): A list of paths with variables to be inferred.
        - database_name (str | None) :Database to validate the query against. None (default) uses the database configured on the server side.

    Returns:
        - df_list (list): A list of dataframes with columns the variables of the path and rows the valid label combinations.
    '''

    df_list = [] # list to store all the final dataframes
    for path in all_paths_with_vars:
        query_w_labels, _, _ = identify_variables_and_construct_query(path, database_name) 
        try:
            df_var_labels = driver.execute_query(query_w_labels,database_=database_name,result_transformer_=neo4j.Result.to_df)# dataframe with columns the vars of the path and rows the valid label combinations
            df_var_labels_columns = set(df_var_labels.columns)

            entered = False #flag to check if the df_var_labels entered the list

            # Check for joinable DataFrames in the list ( the joinable if nay will be only one)
            matched_indexes = {} # dict of the indexes of the dfs in df_list the df_var_labels matched and the joinable columns
            merged_dfs = [] #list of the merged datadrames with df_var_labels 
            
            for i, df in enumerate(df_list):    
                df_columns = set(df.columns)
                joinable_columns = list(df_var_labels_columns & df_columns)
                if joinable_columns:
                    inner_join = df_var_labels.merge(df, on=joinable_columns, how="inner")
                    merged_dfs.append(inner_join)
                    matched_indexes[i] = joinable_columns

            #Merge the list of merged dataframes into one df
            if merged_dfs:
                merged_df = reduce(lambda left, right: left.merge(right, how='inner'), merged_dfs)

                # Replace the original DataFrames (in the indexes in matched_index) in the list with the joined result
                for index in sorted(matched_indexes.keys(), reverse=True):
                    del df_list[index]

                # Add the new element
                df_list.append(merged_df)
                entered = True
                
            if not entered: #it didnt join , so it didnt enter the list        
                df_list.append(df_var_labels)#No joinable DataFrame found, i leave the df as it is and add it on the list   
        
        except Exception as e:
            # Detects:
            # -Neo.DatabaseError.Statement.ExecutionFailed
            # -Neo.ClientError.Statement.SyntaxError
            _, node_vars, rel_vars = identify_variables_and_construct_query(path, database_name)
            all_vars = node_vars + rel_vars
            df_list.append(pd.DataFrame(columns=all_vars)) 

    return df_list

# def replace_with_labels(path, replacements):
#     """
#     Replace variables inside nodes (parentheses) or relationships (square brackets) 
#     in the query with corresponding values from replacements.
    
#     Args:
#         query (str): The query string where replacements are to be made.
#         replacements (dict): A dictionary where each key is an identifier to be replaced, and each value is the replacement.

#     Returns:
#         str: The updated query with identifiers replaced by their corresponding values from replacements.
#     """
#     # Pattern to match both variables inside parentheses (nodes) and square brackets (relationships)
#     # group(1) recognizes node patterns and group(2) recognizes rel patters
#     # (\w+) → Captures one or more word characters (\w+), which include letters (a-z, A-Z), numbers (0-9), and _ (underscore).
#     pattern = r"\(\s*(\w+)\s*\)|\[\s*(\w+)\s*\]"
#     # Use re.sub to replace variables with corresponding values from the replacements dictionary(only if the values of keys are not empty)
#     return re.sub(pattern, lambda match: (f"({match.group(1)}:{replacements.get(match.group(1))})" if match.group(1) in replacements and replacements.get(match.group(1))!=''# if exists in nodes with labels and also is about node
#                                         else f"[{match.group(2)}:{replacements.get(match.group(2))}]"  if match.group(2) in replacements  and replacements.get(match.group(2))!=''# if exists in rels with labels and also is about rel
#                                         else match.group(0) # as it is
#                                     ), path)


def replace_with_labels(path, replacements):
    """
    Replace variables inside nodes (parentheses) or relationships (square brackets) 
    in the query with corresponding values from replacements. If replacements dict contain empty values then it is replaced () or [].
    
    Args:
        path (str): The query string where replacements are to be made.
        replacements (dict): A dictionary where each key is an identifier to be replaced, 
                             and each value is the replacement.

    Returns:
        str: The updated query with identifiers replaced by their corresponding values from replacements.
    """
    # Pattern to match both variables inside parentheses (nodes) and square brackets (relationships)
    # (\w+) → Captures one or more word characters (\w+), which include letters (a-z, A-Z), numbers (0-9), and _ (underscore).
    pattern = r"\(\s*(\w+)\s*\)|\[\s*(\w+)\s*\]"

    def replacer(match):
        node = match.group(1)  # Captures word inside () nodes
        rel = match.group(2)   # Captures word inside [] rels

        if node:
            if node in replacements:
                value = replacements[node]
                # empty values will be returned only after inference in SchemaValidator
                # return f"({node}:{value})" if value else "()"  # If empty, replace with ()
                return f"({node}:{value})" if value else f"({node})"  # If empty, replace with (node)

        if rel:
            if rel in replacements:
                value = replacements[rel]
                # empty values will be returned only after inference in SchemaValidator
                # return f"[{rel}:{value}]" if value else "[]"  # If empty, replace with []
                return f"[{rel}:{value}]" if value else f"[{rel}]"  # If empty, replace with (rel)

        return match.group(0)  # Default return

    return re.sub(pattern, replacer, path)

# Handle specific cases of cypher queries, label exclusion like ! or variable length *
def extract_relationship_variable_length(query):
    ''' 
    Extracts relationship patterns with variable length from the input query and returns a dictionary mapping each
    original pattern to a list of simplified relationships, repeated according to a specified count.
    Args:
    query (str): The input query containing relationship patterns with variable lengths
                such as [:RELATIONSHIP_LABEL*X..Y{property:value}], where:
                    - RELATIONSHIP_LABEL is the name of the relationship
                    - *X (optional) is the minimum repeat count
                    - ..Y (optional) is an upper bound (ignored in this function)
                    - {property:value} (optional) is a property map

    Returns:
        dict: A dictionary where:
            - keys are the original full relationship strings (including brackets and all modifiers)
            - values are lists of simplified relationship strings (repeated according to X or defaulting to 1),
                with the repeat count and range removed, preserving only the label and properties.
    '''

    pattern = re.compile(r"""
    (
    \[
    \s*                     # optional spaces
    (?:[\w\s]+)?\s*         # optional word(s) with spaces before colon, non-capturing group, optional
    :\s*([\w|\s]+)               # word after colon
    \s*\*\s*                # * with optional spaces around
    (\d+\s*)?               # digit X
    (?:\s*\.\.\s*\d+)?      # optional ..Y with spaces around dots but not inside ..
    (\s*\{[^}]*\})?         # optional {something} with optional spaces before {
    \s*\]                   # closing bracket with optional spaces before ]
    )
""",re.VERBOSE)

    result_dict = {}

    for match in pattern.finditer(query):
        # Entire original match, e.g. [:COMES_FROM*3..8{code:'1'}]
        original_relationship = match.group(1)

        # Relationship label word, e.g. COMES_FROM
        relationship_label = match.group(2)

        # First digit after '*', e.g. 3 in *3..8 or *3
        first_digit = match.group(3)

        # Properties {…}, e.g. {code:'1'}
        properties = match.group(4) or ""

        # Determine digit count for repetition:
        # If * but no digit, treat digit as 1
        if first_digit is None:
            digit = 1
        else:
            digit = int(first_digit)

        # Build replacement without *digit part (remove *X and ..Y)
        replaced_no_digit = f"[:{relationship_label}{properties}]"

        # Store list of replacements repeated 'digit' times
        result_dict[original_relationship] = [replaced_no_digit] * digit

    return result_dict

def process_label_exclusion(driver,matches, element_type):
    """
    Handles label exclusion logic for nodes or relationships.

    Args:
        driver: An instance of the Neo4j driver.
        matches (str): The matches found in the query.
        element_type (str): Either 'node' or 'relationship'.

    Returns:
        dict: Mapping of original match → modified version with label replacement.
    """
    replacements = {}
    metadata = []
    for label_part, props_text in matches:
        label_text = label_part.replace(" ", "").split('!')[1]

        # Build Cypher WHERE clause if any properties exist
        if element_type == 'node':
            match_query = f"""
            MATCH (n:!{label_text})
            UNWIND labels(n) AS label
            WITH DISTINCT label
            RETURN REDUCE(s = '', l IN COLLECT(label) |
                   s + (CASE WHEN s = '' THEN '' ELSE '|' END) + l) AS concatenated_labels
            """
        else:  # relationship
            match_query = f"""
            MATCH ()-[r:!{label_text}]-()
            WITH DISTINCT type(r) AS rel_type
            RETURN REDUCE(s = '', t IN COLLECT(rel_type) |
                   s + (CASE WHEN s = '' THEN '' ELSE '|' END) + t) AS concatenated_labels
            """

        # Run the Cypher query to fetch replacement labels/types
        result, summary,_ = driver.execute_query(
            match_query,
            database_='neo4j',
        )
        replacement_label = result[0]['concatenated_labels']

        full_match = ''.join((label_part, props_text or ''))
        replacements[full_match] = full_match.replace(label_text, replacement_label).replace('!', '')

        if summary.notifications:
            for notification in summary.notifications:
                if notification['code'] in['Neo.ClientNotification.Statement.UnknownLabelWarning',
                                            'Neo.ClientNotification.Statement.UnknownRelationshipTypeWarning']: 
                    # Check if an entry with the same 'code' AND 'description' exists
                    if not any(item['code'] == notification['code'] and item['description'] == notification['description'] for item in metadata):
                        metadata.append({'code': notification['code'], 'description': notification['description']})

    return replacements,metadata

def extract_relationship_variable_length(query):
    ''' 
    Args:
    query (str): The input string containing relationship patterns enclosed in square brackets,
                such as [:RELATIONSHIP_LABEL*X..Y{property:value}], where:
                    - RELATIONSHIP_LABEL is the name of the relationship
                    - *X (optional) is the minimum repeat count
                    - ..Y (optional) is an upper bound (ignored in this function)
                    - {property:value} (optional) is a property map

    Returns:
        dict: A dictionary where:
            - keys are the original full relationship strings (including brackets and all modifiers)
            - values are lists of simplified relationship strings (repeated according to X or defaulting to 1),
                with the repeat count and range removed, preserving only the label and properties.
    '''

    pattern = re.compile(r"""
    (                      # Full pattern
    (                      # Group 1: left arrow
        <-                 # "<-" 
        | -                # or single dash
        |                  # or nothing
    )?
                         
    \s*\[
    \s*                     # optional spaces
    (?:[\w\s]+)?\s*         # optional word(s) with spaces before colon, non-capturing group, optional
    :\s*([\w|\s]+)          # Group 3:word after colon
    \s*\*\s*                # * with optional spaces around
    (\d+\s*)?               # Group 4: digit X
    (?:\s*\.\.\s*\d+)?      # optional ..Y with spaces around dots but not inside ..
    (\s*\{[^}]*\})?         # Group 5: optional {something} with optional spaces before {
    \s*\]\s*                   # closing bracket with optional spaces before ]
    
    
    (                      # Group 6: right arrow
        ->                 # "->"
        | -                # or single dash
        |                  # or nothing
    )?
    
    )
    """,re.VERBOSE)

    result_dict = {}

    for match in pattern.finditer(query):
        # print(match)

        # Entire original match, e.g. [:COMES_FROM*3..8{code:'1'}]
        original_relationship = match.group(1)

        # <- or - or nothing
        left_arrow = match.group(2)
        
        # Relationship label word, e.g. COMES_FROM
        relationship_label = match.group(3)

        # First digit after '*', e.g. 3 in *3..8 or *3
        first_digit = match.group(4)

        # Properties {…}, e.g. {code:'1'}
        properties = match.group(5) or ""

        # -> or - or nothing
        right_arrow = match.group(6)

        # Determine digit count for repetition:
        # If * but no digit, treat digit as 1
        if first_digit is None:
            digit = 1
        else:
            digit = int(first_digit)

        # Build replacement without *digit part (remove *X and ..Y)
        replaced_no_digit = f"[:{relationship_label}{properties}]"

        # Store list of replacements repeated 'digit' times
        result_dict[tuple([original_relationship,left_arrow,right_arrow])] = [replaced_no_digit] * digit

    return result_dict

def process_query_label_exclusion (driver,query):
    """
    Handles label exclusion logic for nodes or relationships.

    Args:
        driver: An instance of the Neo4j driver.
        query (str): The cypher query

    Returns:
        query: The query where !node_label/!relationship_type is replaced by the node_labels or the relationship_types
        metadata: The metadata of Unknown relationship type or node label if exist
    """
    # --- Define your patterns ---
    node_pattern = r"\(\s*(\s*\w*\s*:\s*!\s*\w+\s*(?:\|\s*\w+)*\s*)\s*(\{[^}]*\})?\s*\)"
    rel_pattern = r"\[\s*(\s*\w*\s*:\s*!\s*\w+\s*(?:\|\s*\w+)*\s*)\s*(\{[^}]*\})?\s*\]"

    matches_nodes = re.findall(node_pattern, query)
    matches_rel = re.findall(rel_pattern, query)

    # --- Process node and relationship exclusions ---
    metadata = []
    if matches_nodes:
        node_replacements,metadata_nodes = process_label_exclusion(driver,matches_nodes, 'node')
        for original, replacement in node_replacements.items():
            query = query.replace(original, replacement)
        metadata = metadata + metadata_nodes

    if matches_rel:
        rel_replacements,metadata_rels = process_label_exclusion(driver,matches_rel, 'relationship')
        for original, replacement in rel_replacements.items():
            query = query.replace(original, replacement)
        metadata = metadata + metadata_rels

    return query,metadata

def process_query_variable_length(query):
    """
    Replace variable length pattern to Cypher queries, if exists.

    Args:
        query (str): The cypher query

    Returns:
        query: The query where variable length pattern is replaced by the minimum repeat count.
    """
    replacements= extract_relationship_variable_length(query)
    if replacements:
        # Replacement dict with key the pattern as in the query and value a list of labels to include with length X times
        replacements_text={}
        for k, v in replacements.items():
            # join the relationshio labels with the direction indicated in the cypher query
            pattern = ''.join([k[1] + relationship_label + k[2] + '()' for relationship_label in v])
            # remove the last node
            pattern = pattern.removesuffix("()")
            # add the text to the replacements dict
            replacements_text[k[0]] = pattern
        # Replace it in the query
        for k, v in replacements_text.items():
            query = query.replace(k, v)
    return query
        
