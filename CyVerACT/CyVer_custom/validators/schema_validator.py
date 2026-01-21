import regex as re
import neo4j
from CyVer_custom.utils import *

class SchemaValidator:
    """
    A class to validate Cypher queries against a predefined schema.

    This class ensures that Cypher queries conform to the structural constraints defined in a database schema. 
    It validates whether the nodes, relationships, and paths referenced in a query
    align with the expected schema structure, helping to maintain consistency
    and prevent errors.
    """

    def __init__(self, driver):
        """
        Initialize the validator with a Neo4j driver.

        Args:
            driver: An instance of the Neo4j driver.

        Raises:
            TypeError: If the driver is not a valid Neo4j driver.
        """
        # Check if driver is an instance of the Neo4j GraphDatabase driver
        if not isinstance(driver, neo4j.Driver):
            raise TypeError("Provided driver is not a valid Neo4j driver (instance of neo4j.Driver).")
        
        self.driver = driver

    def __get_path_exists(self,path, database_name):    
            # Build the path exists pattern and return a boolean variable indicating if the path exists and the summary
            query = f'''
                RETURN EXISTS {{
                    MATCH p = {path} 
                }} AS path_exists
            '''
            records, summary, _ = self.driver.execute_query(query, database_=database_name)
            return bool(records[0]['path_exists']),summary
  
    def __check_path_exists(self, pattern, original_path_map, database_name=None):
        """
        Check if the provided pattern exists in the Neo4j Database

        Args:
            pattern (str): cypher pattern
            original_path_map (dict/None): A mapping of all the extracted paths(here pattern) with their original form in the query.If the pattern is not a path the value is None.
            database_name (str | None) :Database to validate the query against. None (default) uses the database configured on the server

        Returns:
            - bool: True if the pattern exists , False otherwise.
            - metadata (list[dict]): A list of dictionaries providing details about unknown labels and relationhip types in the query('Neo.ClientNotification.Statement.UnknownLabelWarning',
                                               'Neo.ClientNotification.Statement.UnknownRelationshipTypeWarning')
                        Each dictionary includes:
                        - 'code' (str): The error or warning code.
                        - 'description' (str): A detailed message describing the issue.
        """
        metadata = [] # Initialize the list of metadata of errors, warnings or notifications 
        try:
            original_path_exists,summary_original_path = self.__get_path_exists(pattern, database_name)
        
            #----------Detect specific types of warnings in the query----------------
            if summary_original_path.notifications:
                for notification in summary_original_path.notifications:
                    if notification['code'] in['Neo.ClientNotification.Statement.UnknownLabelWarning',
                                                'Neo.ClientNotification.Statement.UnknownRelationshipTypeWarning']: 
                        # Check if an entry with the same 'code' AND 'description' exists
                        if not any(item['code'] == notification['code'] and item['description'] == notification['description'] for item in metadata):
                            metadata.append({'code': notification['code'], 'description': notification['description']})
            
            # if pattern = node then path_exists = False only if there are notifications unknown label
            # if pattern = rel then path_exists = False only if there are notifications unknown type
            # if pattern = path then path_exists = False if there are notifications unknown label or type
            #                                            or the path does not exist in the graph
            if not original_path_exists and not metadata:
                '''
                In this case, any node labels and the rel type given are valid, but the path does not exist in the graph.
                If the path exists in the graph db with different direction then the error of WrongDirection raises
                Else if the path includes * we check if it exists with the replaced *X..Y to * then the error of VariableLength raises
                Else if the reversed path includes * we check if it exists with the replaced *X..Y to * then the error of WrongDirection&VariableLength raises
                Else the error of UnknownPath raises
                '''            
                # Get the original path(s) from the query that the path pattern is based on 
                original_paths = original_path_map[pattern]
                for original_path in original_paths:
                    var_len_exists,reversed_var_len_exists=False,False
                    # Replace in the path the -> and <- with -, else it is a path with no direction the no_direction_path=''
                    no_direction_path = pattern.replace('->', '-').replace('<-', '-') if '->' in pattern or '<-' in pattern else ''
                    
                    # if exists * in the original path then replaced *X..Y to *
                    if '*' in original_path:
                        replaced_path_with_zero_or_more_path = re.sub(r'\*\s*\d*(?:\s*\.\.\s*\d+)?', '*', original_path) if '*' in original_path else original_path
                        var_len_exists,_ = self.__get_path_exists(replaced_path_with_zero_or_more_path, database_name)

                    #----------Conditions----------------#
                    # If the original path replaced *X..Y to * exists then raises VariableLengthPathWarning
                    if var_len_exists:
                        metadata.append({'code': 'VariableLengthPathWarning', 
                                                    'description': f'The specified path {self.__replace_variables_with_empty_string(pattern)} does not exist in the knowledge graph schema. The path {original_path} in the Cypher statement should be changed to {replaced_path_with_zero_or_more_path}.'})
                    # If the original path with replaced * not fix NOT exists then check the reversed direction path 
                    # If the reversed direction path exists then WrongDirectionPathWarning raises
                    # Else if the reversed direction path path NOT exists then:
                    #   if the the reversed direction path exists then the WrongDirectionPath&VariableLengthPathWarning raises
                    #   else raises the UnknownPath warning
                    elif no_direction_path:
                        no_direction_path_exists,_ = self.__get_path_exists(no_direction_path, database_name)
                        if '<-' in original_path:
                            # reverse from left to right
                            parts = re.split(r'<-\s*|\s*-\s*', original_path)
                            reversed_path = f"{parts[0]}-{parts[1]}->{parts[2]}"
                        elif '->' in original_path:
                            # reverse from right to left
                            parts = re.split(r'\s*->\s*|\s*-\s*', original_path)
                            reversed_path = f"{parts[0]}<-{parts[1]}-{parts[2]}"
                        
                        # If the no_direction is True, then we have to switch the direction (WrongDirectionPathWarning)
                        if no_direction_path_exists:
                            # Switch the direction to the original path in the query
                            metadata.append({'code': 'WrongDirectionPathWarning', 'description': f'The specified path {self.__replace_variables_with_empty_string(pattern)} has the opposite direction in the knowledge graph schema. The path {original_path} in the Cypher statement should be changed to  {reversed_path}.'})                                  
                        # Else, if the path not exists with reversed direction in the graph db
                        else:
                            if '*' in reversed_path:
                                reversed_var_len_path = re.sub(r'\*\s*\d*(?:\s*\.\.\s*\d+)?', '*', reversed_path)
                                reversed_var_len_exists,_ = self.__get_path_exists(reversed_var_len_path, database_name)
                            # Then, we check if the path exists with reversed direction and replaced *X..Y to *
                            if reversed_var_len_exists:
                                metadata.append({'code': 'WrongDirectionPath&VariableLengthPathWarning',
                                                    'description': f'The specified path {self.__replace_variables_with_empty_string(pattern)} does not exist in the knowledge graph schema. The path {original_path} in the Cypher statement should be changed to {reversed_var_len_path}.'})  
                            else:
                                metadata.append({'code': 'UnknownPathWarning', 'description': f'The specified path {self.__replace_variables_with_empty_string(pattern)} does not exist in the knowledge graph schema. The path {original_path} in the Cypher statement is wrong.'})                                          
                    # Else the direction of path or/and the replaced * doesn't fix the path then UnknownPathWarning (path with no directions)
                    else:
                        metadata.append({'code': 'UnknownPathWarning', 'description': f'The specified path {self.__replace_variables_with_empty_string(pattern)} does not exist in the knowledge graph schema. The path {original_path} in the Cypher statement is wrong.'})                                  
            return original_path_exists, metadata
        except Exception as e:
                # Syntax or Execution error, the query with the given pattern cannot be executed
                original_path_exists =  False
                # metadata.append({'code': e.code, 'description': e.message})
                return original_path_exists, metadata

    def __extract_internal(self, query, database_name=None):
        """
        Extract the node labels, relationship types and one-hop paths of the provided query. Any properties mentioned are stripped. 

        Args:
            query (str): The Cypher query to validate.
            database_name (str | None) :Database to validate the query against. None (default) uses the database configured on the server side.

        Returns:
            A list of the nodes, 
            A list of the relationships
            A list of the paths in the cypher query 
            A dict with mapping of the original paths from the query and the extracted paths (paths only with labels, rels (inferred or not))
            A list of metadata if exist label that do not exist in the graph db
        """

        # mappping of the original path (as it is in the query) with the path the extractor returns (key: edited path, value: list of original paths)
        original_path_map = {} 
        # mapping of the path before and after inference
        inference_path_map = {}

        # pattern of nodes in the form (var:Label {props} or var:Label1|Label2{props} pr var:!Label1) Optional variable Optional label Optional properties
        node_pattern = r"""
        \(
            \s*                                     # Optional whitespace after opening (
            (?:                                     # Start non-capturing group for content
            # Catches the n:label1 or n:!label1|label2 n:!label1|!label2 or without n
                \s*\w*\s*                           # Optional variable (e.g., n)
                :                                   # Colon separator
                \s*!?\s*\w+                         # Optional '!' + label
                (?:\s*\|\s*!?\w+)*                  # Optional additional '|' separated labels (with optional '!')(*-> zero or more)
                \s*                                 # Optional whitespace
            # Catches just a variable n
            | \s*\w+\s*                            # OR just a variable
            # Catches empty
            |                                      # OR empty
            )
            (?:\{[^}]*\})?                           # Optional properties in curly braces
            \s*                                      # Optional whitespace before closing )
        \)
        """

        # pattern of relationships in the form [var:REL {props}] Optional variable Optional label Optional properties
        rel_pattern = r"""
        \[
            \s*                                     # Optional whitespace after opening (
            (?:                                     # Start non-capturing group for content
            # Catches the n:label1 or n:label1|label2 or n:label1|label2*X..Y or without n
                \s*\w*\s*                           # Variable
                :                                   # Colon separator
                \s*\w+                              # label
                (?:\s*\|\s*\w+)*                    # Optional additional '|' separated labels (*-> zero or more)
                (?:                                 # Optional repetition pattern (*, *X, *X..Y)
                    \s*\*                           # Asterisk
                    \s*\d*                          # Optional X
                    (?:\s*\.\.\s*\d+)?              # Optional ..Y
                )?
                \s*                                 # Optional whitespace 
            # Catches the n:!label or n:!label1|label2 or without n
            |\s*\w*\s*                              # Variable
            :                                       # Colon separator
            \s*!?\s*\w+                             # ! Label
            (?:\s*\|\s*!?\w+)*                      # Optional additional '|' separated labels with optional ! (*-> zero or more)
            # Catches just a variable n
            | \s*\w+\s*                           # OR just a variable
            #Catches empty
            | 
            )
            (?:\{[^}]*\})?                           # Optional properties in curly braces
            \s*                                      # Optional whitespace before closing )
        \]
        """

        ################### Original paths ##################################
        # Extract the paths as it is in the query (original paths)
        path_pattern_original = rf"({node_pattern}\s*(?:<?\s*-\s*(?:{rel_pattern})?\s*-\s*>?|\s*<\s*-\s*-\s*|\s*-\s*-\s*>\s*|\s*-\s*-\s*)\s*{node_pattern})"

        # Extract paths in their original form(as they are in the query)
        matches_original = re.findall(path_pattern_original,query,re.VERBOSE,overlapped=True)

        ################## Edited paths #####################################
        # Replace -- with empty relationship to infer the hidden relationship
        query = query.replace("--", "-[]-")

        # Replace () with (unknown variables)
        query = self.__replace_bracket_placeholders(query)

        # combine node and relationships patterns
        path_pattern= rf'({node_pattern}\s*<?\s*-\s*{rel_pattern}\s*-\s*>?\s*{node_pattern})'

        # Extract paths
        matches = re.findall(path_pattern,query,re.VERBOSE,overlapped=True)

        # specify only node if no detected relationships without ? after :, only nodes with labels
        nodes_with_label = r"""
        \(
            \s*                                     # Optional whitespace after opening (
            (                                       # Group 1: n:label1 or n:!label1|label2
                \s*\w*\s*                           # Optional variable (e.g., n)
                :                                   # Colon separator
                \s*!?\s*\w+                         # Optional '!' + label
                (?:\s*\|\s*!?\w+)*                  # Optional additional '|' separated labels (with optional '!')(*-> zero or more)
                \s*                                 # Optional whitespace
            )
            \s*
            (\{[^}]*\})?                           # Group 2
            \s*                                    # Optional whitespace before closing )
        \)
        """

        # specify only node if no detected relationships without * after :, only nodes with labels
        rels_with_label = r"""
        \[
            \s*                                     # Optional whitespace after opening (
            (                                       # Group 1: n:label1 or n:label1|label2 or n:label1|label2*X..Y or without n
                \s*\w*\s*                           # Variable
                :                                   # Colon separator
                \s*\w+                              # label
                (?:\s*\|\s*\w+)*                    # Optional additional '|' separated labels (*-> zero or more)
                (?:                                 # Optional repetition pattern (*, *X, *X..Y)
                    \s*\*                           # Asterisk
                    \s*\d*                          # Optional X
                    (?:\s*\.\.\s*\d+)?              # Optional ..Y
                )?
                \s*                                 # Optional whitespace 
            # Catches the n:!label or n:!label1|label2 or without n
            |\s*\w*\s*                              # Variable
            :                                       # Colon separator
            \s*!?\s*\w+                             # ! Label with optional !
            (?:\s*\|\s*!?\w+)*                      # Optional additional '|' separated labels with optional ! (*-> zero or more)
            )
            (\{[^}]*\})?                           # Group 2: Optional properties in curly braces
            \s*                                    # Optional whitespace before closing )
        \]
        """

        # Extract labeled nodes and relationships using regex
        nodes_matches = re.findall(nodes_with_label, query,re.VERBOSE)
        rels_matches = re.findall(rels_with_label, query,re.VERBOSE)

        # Dict of key the variables in query and value the label of the rel or node
        nodes_dict = {key.strip() or f"_empty_{i}": value.strip() for i, (key, value) in enumerate(match[0].split(":", 1) for match in nodes_matches)}
        rels_dict = {key.strip() or f"_empty_{i}": value.strip() for i, (key, value) in enumerate(match[0].split(":", 1) for match in rels_matches)}
        elements_dict = {**nodes_dict, **rels_dict}

        # The nodes labels
        node_labels = list(set(nodes_dict.values()))
        node_paths = ['(:' + node_label + ')' for node_label in node_labels]

        # The rels labels
        rel_labels = list(set(rels_dict.values()))
        # Delete everything after * if exists
        rel_paths = ['()-[:' + re.sub(r'\*.*', '' ,rel_label) + ']-()' for rel_label in rel_labels]
        rel_paths = list(set(rel_paths))

        # If we have at least one path in the cypher query
        if matches:
            # A set containing the paths for inference
            inference_paths,paths = set(),set()

            # Stage 1: Replace identifiers in already mentioned in the cypher query, remove {} and prepare for inference!
            for index, match in enumerate(matches):
                # Step 1: Delete extra spaces
                path = re.sub(r'\s+','',match)

                # Step 2: Delete {} properties inside nodes and rels
                match_wt_prop = re.sub(r"\{[^}]*\}", "", path)
                
                # Step 3: Add labels to variables if specified in another match clause
                path_with_node_rels_labels = replace_with_labels(match_wt_prop, elements_dict) # replace i to i:Indicator

                # Step 4: Remove prefix before colon to the edited path
                edited_path = self.__remove_prefix_before_colon(path_with_node_rels_labels) 

                # Step 5: Inference - Find variables in relationships or nodes
                if any(filter(None, re.findall(r"\((\w+)\)|\[(\w+)\]", path_with_node_rels_labels))):
                    # add to inference paths
                    inference_paths.add(edited_path)
                    #keep a mapping before and after inference
                    inference_path_map[edited_path] = ''

                # Step 6: Add the edited path to paths
                paths.add(edited_path)
                        
                # Step 7: Keep a mapping of the edited path with the original paths (the edited path may appear to more than one original paths)
                original_path_map.setdefault(edited_path, []).append(matches_original[index])
                
                # Step 7: Isolate not inference paths
                not_inference_paths = paths - inference_paths

            # Stage 2: Inference time!
            if inference_paths:
                # Copy not inference paths to combine them
                paths_after_inference = not_inference_paths.copy()
                # Create a dict with key the unknown variable and value a random variable from the df if is not empty else ""
                inference_dict={}
                for df in get_paths_after_inference(self.driver,list(inference_paths),database_name):
                    if df.empty:
                        for col in df.columns:
                            inference_dict[col]=""
                    else:
                        df1_inf = df.sample(1).reset_index(drop=True)
                        for col in df.columns:
                            inference_dict[col] = df1_inf.iloc[0][col]
                # Loop over the inference paths to replace with labels
                for inference_match in inference_paths:
                    inferenced_path = self.__remove_prefix_before_colon(replace_with_labels(inference_match,inference_dict))
                    paths_after_inference.add(inferenced_path)
                    #update the mapping dict before and after inference of the path 
                    inference_path_map[inference_match] = inferenced_path
                
                # Update original_path_map to map the original path to the inferenced path
                updated_original_path_map = {}
                for modified_path in original_path_map:
                    # If the edited/modified path is a path that needs to be inferenced then:
                    if modified_path in inference_path_map:
                        # get the modified inferenced path as key and value the original paths
                        updated_original_path_map[inference_path_map[modified_path]] = original_path_map[modified_path] 
                    else:
                        # otherwise, add as key the modified path and value the original paths
                        updated_original_path_map[modified_path] = original_path_map[modified_path]
                        
                # Replace the old mapping with the updated one
                original_path_map =  updated_original_path_map
                return node_paths,rel_paths,list(paths_after_inference), original_path_map
            return node_paths,rel_paths,list(paths), original_path_map
        else:
            return node_paths,[],[], original_path_map
    
    def extract(self,query, database_name=None):
        """
        Extract the node labels, relationship types and one-hop paths of the provided query. Any properties mentioned are stripped. 

        Args:
            query (str): The Cypher query to validate.
            database_name (str | None) :Database to validate the query against. None (default) uses the database configured on the server side.

        Returns:
            Three lists containing the nodes, the relationships and the paths in the cypher query
        """
        nodes, rels, paths, maps= self.__extract_internal(query, database_name)
        paths = [self.__replace_variables_with_empty_string(path) for path in paths]
        return nodes, rels, paths,maps
        
    def validate(self,query, database_name=None):
        """
        Validate the correctness of the nodes, relationships and paths of the provided query

        Args:
            query (str): The Cypher query to validate.
            database_name(str | None): The name of the database to validate the query against. None (default) uses the database configured on the server side.

        Returns:
            A score in [0,1] : a weighted average of the correct nodes,relationships and paths with equal weights
        """
        #Extract from the query the node labels, the relationship types, and the one-hop paths only with node labels and rel types
        #and the mapping of the extracted one-hop path with th eoriginal one-hop path in the query 
        nodes, rels, paths, original_path_map = self.__extract_internal(query, database_name)

        metadata =  set()  # Use a set to store unique notifications of metadata of errors, warnings or notifications

        if nodes:
            common_nodes = 0 
            for node in nodes:
                node_exists, node_notifications = self.__check_path_exists(node, None, database_name)
                common_nodes += int(node_exists)  # Convert boolean to integer and sum it
                if node_notifications:
                   # Neo.ClientNotification.Statement.UnknownLabelWarning
                    metadata.update(tuple(notification.items()) for notification in node_notifications)
        if rels:
            common_rels = 0 
            for rel in rels:
                rel_exists, rel_notifications = self.__check_path_exists(rel,None, database_name)
                common_rels += int(rel_exists)  
                if rel_notifications:
                    # Neo.ClientNotification.Statement.UnknownRelationshipTypeWarning
                    metadata.update(tuple(notification.items()) for notification in rel_notifications)
        if paths: 
            common_paths = 0 
            for path in paths:
                path_exists, path_notifications = self.__check_path_exists(path,original_path_map, database_name)
                common_paths += int(path_exists)  
                if path_notifications:
                    # Neo.ClientNotification.Statement.UnknownLabelWarning
                    # Neo.ClientNotification.Statement.UnknownRelationshipTypeWarning
                    metadata.update(tuple(notification.items()) for notification in path_notifications)
        
        # Convert to list
        metadata = [dict(notification) for notification in metadata]
        # Calculate the score based on the number of common nodes, relationships, and paths
        # The score is a weighted average of the correct nodes,relationships and paths with equal weights
        if paths:
            if nodes:
                if rels:               
                    score = 1/3 * ((common_rels) / len(rels)) + 1/3 * ((common_nodes) / len(nodes)) + 1/3 * ((common_paths) / len(paths))

                else:
                    score = 0.5 * ((common_nodes) / len(nodes)) +  0.5 * ((common_paths) / len(paths))

            else:
                if rels:
                    score = 0.5 * ((common_rels) / len(rels)) + 0.5 * ((common_paths) / len(paths))
                else:
                    score = ((common_paths) / len(paths))
                    # raise ValueError("Both 'rels' and 'nodes' lists are empty while existing paths")
        else:
            if nodes:
                score = ((common_nodes) / len(nodes))
            else:
                # match (n) case
                score = 1

        return score, metadata

    # This method does not require access to any instance or class data. It is  purely a utility function that performs an operation (addition) and 
    # returns the result. Static methods are typically used when the method does not need to modify or access the object's state.
    @staticmethod
    def __remove_prefix_before_colon(txt):
        """
        Remove prefix before colon

        Args:
            txt (str): a:example

        Returns:
            :example
        """
    # Regex to remove anything before the colon in both nodes and relationships
        return re.sub(r'\b\w+:(\w*)', r':\1', txt)
    
    @staticmethod
    def __replace_bracket_placeholders(query):
        counter = [0]  # use list so inner function can modify it

        pattern = re.compile(r'''
            (\<\s*-|-|-\s*>)       # group 1: left arrow or dash
            \s*           # optional spaces
            ([\(\[])\s*   # group 2: opening bracket ( or [
            \s*           # optional spaces
            ([\)\]])      # group 3: closing bracket ) or ]
            \s*           # optional spaces
            (-\s*>|-|<\s*-)        # group 4: right arrow or dash
        ''', re.VERBOSE)

        def replacer(match):
            counter[0] += 1
            left = match.group(1)
            open_bracket = match.group(2)
            close_bracket = match.group(3)
            right = match.group(4)
            return f"{left}{open_bracket}var_{counter[0]}{close_bracket}{right}"

        return pattern.sub(replacer, query)

    @staticmethod
    def __replace_variables_with_empty_string(pattern):
        return re.sub(r"\(\s*\w+\s*\)|\[\s*\w+\s*\]", lambda m: "()" if m.group(0).startswith('(') else "[]", pattern)    
