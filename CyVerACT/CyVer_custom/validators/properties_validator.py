import neo4j
import regex as re
import pandas as pd
from CyVer_custom.utils import *

class PropertiesValidator:
    """
    A class to validate the correctness of property access in Cypher queries against a predefined schema.

    This class ensures that Cypher queries access only valid properties for nodes
    and relationships based on their labels or types.
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

    def __check_label_type(self, label, database_name=None):
        """
        Check if a given label is a node label or a relationship type.
        Args:
            - label(string): The label to check.
            - database_name (str | None) :Database to validate the query against. None (default) uses the database configured on the server side.
        Returns:
            string: "node" or "relationship", "none" otherwise.
        """
        # Query for node labels
        node_query = f"""
        CALL db.labels()
        YIELD label
        WHERE label = '{label}'
        RETURN COUNT(label) > 0 AS is_node_label
        """
        
        # Query for relationship types
        rel_query = f"""
        CALL db.relationshipTypes()
        YIELD relationshipType
        WHERE relationshipType = '{label}'
        RETURN COUNT(relationshipType) > 0 AS is_relationship_type
        """
        
        # Execute both queries
        try:
            node_result = self.driver.execute_query(node_query, database_= database_name)
            rel_result = self.driver.execute_query(rel_query, database_= database_name)
            
            # Determine the type
            is_node_label = node_result[0][0]['is_node_label'] if node_result else False
            is_relationship_type = rel_result[0][0]['is_relationship_type'] if rel_result else False
            
            # Return the result
            if is_node_label:
                return "node"
            elif is_relationship_type:
                return "relationship"
            else:
                return "none"
        except Exception as e:
            # Syntax or Execution error, the query with the given pattern cannot be executed
            return "none"
        
    def __query_prop_exist(self, label, property, database_name = None):
        '''Check if this property exists for the defined label
        Args:
            - label(str): The label to check.
            - property (str): The property to check.
            - database_name (str | None) :Database to validate the query against. None (default) uses the database configured on the server side.
            
        Returns:
            - bool: True if the property exists , False otherwise.
            - metadata (list[dict]): A list of dictionaries providing details about unknown property accesses in the query(Neo.ClientNotification.Statement.UnknownPropertyKeyWarning)
                                    Each dictionary includes:
                                    - 'code' (str): The error or warning code.
                                    - 'description' (str): A detailed message describing the issue.
        '''
        property_exists = False
        metadata = []
        type = self.__check_label_type(label, database_name)
        if type != 'none': # the label does not exist in the graph
            if type=='node':
                check_cypher = f"RETURN exists {{ MATCH (x:{label}) WHERE (x.{property}) IS NOT NULL}} AS exists"
            elif type=='relationship':
                check_cypher = f"RETURN exists {{ MATCH ()-[x:{label}]-() WHERE (x.{property}) IS NOT NULL}} AS exists"
            try:
                records, summary, _ = self.driver.execute_query(check_cypher,database_=database_name)
                #----------Detect specific types of warnings in the query----------------
                if summary.notifications:
                    for notification in summary.notifications:
                        if notification['code'] == 'Neo.ClientNotification.Statement.UnknownPropertyKeyWarning': 
                            metadata.append({'code': notification['code'], 'description': notification['description']})
                                    
                property_exists = records[0]['exists']
            except Exception as e:
                # Syntax or Execution error, the query with the given pattern cannot be executed
                return property_exists, metadata
        return property_exists, metadata
    
    def __get_inferred_labels_properties (self,strict, var_label_map,label_props_map, var_props_map, query, database_name=None):
        '''
        Infers labels for variables that are missing labels but access properties and updates the label_props_map dict(that 
        maps the labels with the properties they access) with the inferred labels for variables that lacked them and their accessed properties .

        Args:
        - strict (bool): Determines the behavior of the function when trying to match labels:
            - If True, the function will only return the first valid label-property pair that correctly matches all properties.
            - If False, the function will return the label-property pair that matches the most properties correctly, even if some properties remain unmatched.
        - var_label_map (dict): A mapping of variables to their corresponding labels.
        - label_props_map (dict): A mapping of labels to the properties they access.
        - var_props_map (dict): A mapping of variables to the properties they access.
        - query (str): The query used for inference, which may be utilized to gather further data.
        - database_name (str | None): The name of the database to validate the query against. None (default) uses the database configured on the server side.

        Returns:
        - dict: A dictionary containing the inferred label-property mappings, where the labels are the inferred ones for unknown variables.
        '''
        # Infer the unknown variables
        inference_paths = self.__prepare_query_for_infer (var_label_map, query)
        df_valid_label_pairs = get_paths_after_inference (self.driver,inference_paths, database_name) #list of df with inferred labels of vars 
        for df_var_labels in df_valid_label_pairs:
            #keep the columns(inferred labels) of the unknown variables that access properties
            cols_to_keep = [col for col in df_var_labels.columns if col in var_props_map]
            if cols_to_keep:
                df_filtered = df_var_labels[cols_to_keep].drop_duplicates()
            else:
                df_filtered = pd.DataFrame()  
            
            #If the df has one row (then the variable has to be a specific label)
            if len(df_filtered.index) == 1:
                #---ALWAYS STRICT=FALSE APPROACH-----
                # for var in  df_filtered.columns:
                #     label = df_filtered[var].iloc[0]
                #     #add to the label_props_map the properties accessed by this label (infereed by the var)
                #     label_props_map = self.__extend_dict_with_list_elements (label_props_map, label, var_props_map[var])
                #--------------------------------------

                valid_label = True #All the labels have all their properties valid
                label_props = {} #Each inferred label which properties accesses based on the var(var_props_map)
                for variable in  df_filtered.columns:
                    label = df_filtered[variable].iloc[0] # map the variable to the label
                    #the label accesses these properties
                    label_props = self.__extend_dict_with_list_elements (label_props, label, var_props_map[variable])
                    for accessed_prop in var_props_map[variable]:
                        #check if ALL the properties accessed by this label are valid
                        property_exists, _ = self.__query_prop_exist(label, accessed_prop, database_name)
                        if not property_exists:
                            valid_label = False #at least one property of one label of the label pairs is not valid
                if valid_label:
                    # print('The label has all its properties valid')
                    #add to the label_props_map the properties accessed by this label (inferred by the var)
                    label_props_map = self.__extend_dict_with_list_elements (label_props_map, label, label_props[label])
                else:
                    #if strict: i dont care about these properties
                    if not strict:
                        #i return the label 
                        label_props_map = self.__extend_dict_with_list_elements (label_props_map, label, label_props[label])
            elif len(df_filtered.index) > 1: #if it has multiple pairs of valid labels
                #  we need to find at least one pair for which all the accessed properties are valid
                # if none pair is found we return the pair that offers the max accessed properties  
                label_pair_correct_props = {} #map each label pair(row of df) with total number of correct props accessed     
                for index, row in df_filtered.iterrows():
                    total_correct_props = 0 #counter per row (label pairs) with correct properties, used when a valid label pair for all properties was not found)
                    #For dependend variables (columns of the dataframe) the properties accessed have to be valid for all labels
                    valid_label = True #All the labels have all their properties valid
                    label_props = {} #Each inferred label which properties accesses based on the var(var_props_map)
                    for variable in  df_filtered.columns:
                        label = row[variable] # map the variable to the possible label
                        #the label accesses these properties
                        label_props = self.__extend_dict_with_list_elements (label_props, label, var_props_map[variable])
                        for accessed_prop in var_props_map[variable]:
                            #check if ALL the properties accessed by this label are valid
                            property_exists, _ = self.__query_prop_exist(label, accessed_prop, database_name)
                            if not property_exists:
                                valid_label = False #at least one property of one label of the label pairs is not valid
                            else:
                                total_correct_props+=1 
                    label_pair_correct_props[index] = total_correct_props  
                    if valid_label:
                        # print('All the labels have all  their properties valid')
                        
                        #add the valid pair of labels and their properties
                        for label in label_props:
                            label_props_map = self.__extend_dict_with_list_elements (label_props_map, label, label_props[label])
                        break #stop searching the label pairs
                if not valid_label:
                    #if strict: i dont care about these properties                    
                    if not strict :
                        #i get the label pair that accesses the max correct properties
                        
                        max_index = max(label_pair_correct_props, key=label_pair_correct_props.get)
                        label_props = {}
                    
                        for variable in  df_filtered.columns:
                            label = df_filtered.loc[max_index, variable]
                            #the label accesses these properties
                            label_props = self.__extend_dict_with_list_elements (label_props, label, var_props_map[variable])
                        
                        for label in label_props:
                            label_props_map = self.__extend_dict_with_list_elements (label_props_map, label, label_props[label])
                                
        return label_props_map
    
    def __infer_disjoint_labels(self,var_label_map,label_props_map,query, database_name):
        '''
        Detects labels in disjunciton  (e.g., Label1|Label2) that access properties and infers based on the properties the final label.
        It updates the label_props_map and var_labels_map with the updated final label in place of the disjoint labels, and the query.
        If all the properties accessed by the disjoint labels are valid for all the labels, then the updated final label remains the disjoint label.
        Otherwise the updated final label if the one (or more in disjoint) with the maximum valid accessed labels.
        Args:
        - var_label_map (dict): A mapping of variables to their corresponding labels.
        - label_props_map (dict): A mapping of labels to the properties they access.
         - query (str): The query used for inference, which may be utilized to gather further data.
        - database_name (str | None): The name of the database to validate the query against. None (default) uses the database configured on the server side.

        Returns:
        - var_label_map(dict): The updated version of var_label_map
        - label_props_map: The updated version of label_props_map
        - query(str): The updated version of the query
        '''
        for examined_label in label_props_map.copy():
            if '|' in examined_label:#Find the disjoint labels(Label1|Label2|...)
                disjoint_labels = examined_label.split('|')
                properties_accessed = label_props_map[examined_label]

                label_pair_correct_props = {} #map each label (of the disjoint) with total number of correct props accessed 
                valid_label = True #All the labels have all their properties valid
                for label in disjoint_labels:
                    total_correct_props = 0 #counter per label with correct properties, used when a valid label for all properties was not found
                    for accessed_prop in properties_accessed:
                        #check if ALL the properties accessed by this label are valid
                        property_exists, _ = self.__query_prop_exist(label, accessed_prop, database_name)
                        if not property_exists:
                            valid_label = False #at least one property of one label of the disjoint labels is not valid
                        else:
                            total_correct_props+=1 
                    label_pair_correct_props[label] = total_correct_props          
                if not valid_label: #there are labels that are not valid for all the propertiesk, so we pick labels with the  max valid properties
                    #keep the labels that access the majority of properties correctly
                    # Find the maximum value
                    max_correct_props = max(label_pair_correct_props.values())

                    # Get all labels with that max value
                    selected_labels = [i for i, v in label_pair_correct_props.items() if v == max_correct_props]

                    if len(selected_labels) ==1: #only one label had max
                        updated_label = selected_labels[0]
                    else: #keep the labels with max in disjoint
                        updated_label = '|'.join(selected_labels)
                    
                    # 1: Update var_labels_map
                    for var, label in var_label_map.items():
                        if label == examined_label:
                            var_label_map[var] = updated_label

                    # 2: Update label_props_map
                    if examined_label in label_props_map:
                        label_props_map[updated_label] = label_props_map.pop(examined_label)
                    
                    # 3: Update the query
                    query = query.replace(examined_label, updated_label)

        return var_label_map, label_props_map, query

    def __get_var_labels_props (self, query, database_name):
        '''
        It extracts from query vars, labels and props and returns the mapping:
        - variables with labels
        - labels with properties
        - unknown variables with properties
        Args:
            query(str): The query to be validated
        Returns
            Dict (var_label_map) that maps any variables with their labels 
            Dict (labels_props_map), that maps labels with properties they access
            Dict (var_props_map), that maps variables unmatched with any label, with the properties they access

        '''
        # Remove *x..y in relationships, if any
        query = re.sub(r'\*\s*\d*(?:\s*\.\.\s*\d+)?', '', query)

        # If there are exlusion labels (e.g., !Label) we replace them with labels in disjunction based on the KG schema 
        query, _ = process_query_label_exclusion (self.driver,query)

        # Get labels and variables that access properties in the query
        var_label_map, label_props_map = PropertiesValidator.__inline_var_label_properties_mapping(query)
        label_props_map, var_props_map = PropertiesValidator.__outside_var_properties_mapping(var_label_map, label_props_map,query)
        
        # If there are labels or types in disjunction (e.g., Label1|Label2|...) that access property, we need to infer the final label and update the query
        var_label_map, label_props_map, query = self.__infer_disjoint_labels(var_label_map,label_props_map,query, database_name)
        
        return var_label_map, label_props_map, var_props_map
    
    def extract(self,query,database_name = None, strict=False):
        """
        Extract the properties accessed by each label of the provided query

        Args:
            query (str): The Cypher query to validate.
            strict (bool): Determines the behavior of the function when trying to infer labels:

        Returns:
            Mappings of:
                var_props_map: variables with properties they access
                label_props_map: labels (inferred and not) with the properties they access
        """
        #Get the properties accessed by each label (label_props_map)
        var_label_map, label_props_map, var_props_map = self.__get_var_labels_props (query,database_name)
        
        # If there are variables with no matched labels that access properties, we need to infer their labels
        if var_props_map:
            label_props_map = self.__get_inferred_labels_properties (strict, var_label_map,label_props_map, var_props_map, query, database_name)
        
        return var_props_map,label_props_map
    
    def validate(self,query,database_name = None, strict=False):
        """ 
        Validate the correctness of the properties accessed by labels  in the given query against the provided schema.

        Args:
            query (str): The Cypher query to validate.
            database_name (str | None): The name of the database to validate the query against. None (default) uses the database configured on the server side.
            strict (bool): Determines the behavior of the function when trying to infer labels:

        Returns:
            -Precission score in [0,1] : of the correct_props / total_props
            or None if there were no properties accessed
           metadata (list[dict]): A list of dictionaries providing details about invalid property accesses in the query.  
                       This includes properties that are incorrectly associated with specific labels,  
                       as well as properties that do not exist in the database  
                       (e.g., Neo.ClientNotification.Statement.UnknownPropertyKeyWarning).  
                Each dictionary includes:  
                - 'code' (str): The error or warning code.  
                - 'description' (str): A detailed message describing the issue.  
        """
        metadata = [] #initialize the list of metadata of errors, warnings or notifications
        _, label_props_map = self.extract(query,database_name, strict)
        # print(label_props_map)
        if label_props_map:
            correct_props = 0 # How many of the total properties accessed are valid according to their label
            incorrect_label_props_map = {}  #Which accessed properties are not valid for the labels (inferred or not) in the query

            for label, properties in label_props_map.items():       
                #If the label is disjoint (e.g. Label1|Label2|..) we keep only one of them for the computation of properties validity 
                # (since in this stage all labels kept in disjoint have the same num of correct properties)
                if '|' in label:#Find the disjoint labels(Label1|Label2|...)
                    label = label.split('|')[0]
                for property in properties:
                    property_exists, notifications = self.__query_prop_exist(label, property, database_name)
                    if property_exists:
                        correct_props += 1
                    else:
                        incorrect_label_props_map = self.__extend_dict_with_list_elements(incorrect_label_props_map, label, [property])
            
                    if notifications: #add the notifications of unknown property warning in the matadata list
                        metadata.extend(notifications)

            total_props = sum(len(properties) for properties in label_props_map.values())

            # Calculate precision
            precision = correct_props / total_props #if total_props > 0 else 1
            if precision < 1:
                for label, props in incorrect_label_props_map.items():
                    metadata.append( {'code': 'InvalidPropertyAccessByLabelWarning', 
                                    'description': f'The label {label} does not have the following properties:  {", ".join(props)}.'
                                    })
            return precision , metadata
        
        return None, metadata #if no property was accessed

    @staticmethod
    def __extend_dict_with_list_elements (mydict, key, list_value):
        ''' 
        Add to mydict a new key if it doesnt exist with value the given list
        If the key exists extend the value list with no duplicate elements of the given list
        Args:
        - mydict (dict): The dictionary to modify.
        - key (hashable): The key to check or add.
        - list_value (list): The list of elements to add or extend.

        Returns:
        - mydict: The modified dictionary .
        '''
        if key not in mydict:
            mydict[key] = list_value
        else: 
            mydict[key].extend(
                prop for prop in list_value if prop not in mydict[key]
            )
        return mydict
    
    @staticmethod
    def __inline_var_label_properties_mapping ( query ):
        """ 
        Extracts from the query the mapping of nodes and relationship labels with their properties
        (properties accessed inside) and the mapping of variables and labels.
        
        The pattern matched: matches = [('var:Label','{ property_name : property_value}'), ...]
        
        Args:
            query (str): The Cypher query to validate.
        Returns:
            Dict (labels_props_map) that maps the label (of a node or a relationship ) with a list of its properties 
            accessed in the query 
            Dict (var_label_map) that maps any variables with their labels 
        """

        label_props_map = {} #Map each label with the properties mentioned
        var_label_map = {} #Map each var with the label mentioned (in case the variable is mentioned again without its label)

        #Find patterns of nodes or relationships that define their label
         # To match a node: optional_variable:label{optional properties} (label can be one or more labels (e.g., :Label1 or :Label1|Label2))
        node_pattern = r"\(\s*(\w*\s*:\s*\w+(?:\s*\|\s*\w+)*)\s*(\{[^}]*\})?\s*\)"
        # To match a relationship: optional_variable:type{optional properties}  (type can be one or more types (e.g., :Type1 or :Type1|Type2))
        rel_pattern = r"\[\s*(\w*\s*:\s*\w+(?:\s*\|\s*\w+)*)\s*(\{[^}]*\})?\s*\]"
        # Match nodes and relationships separately
        node_matches = re.findall(node_pattern, query)
        rel_matches = re.findall(rel_pattern, query)
        matches = [ match for match in node_matches] + [ match for match in rel_matches]
        # matches = [('var:Label','{ property_name : property_value}'), ...]

        #-------------------------------------------------------------------------------------
        #---------For properties accessed inside the node or relationship --------------------
        #-------------------------------------------------------------------------------------
        label_pattern = r":(.*)" #extract the label name
        var_pattern = r"(.*):" #extract the var
        property_pattern = r"\b(\w+)\s*:" #extract the property name (up to :) from the properties accessed inside 

        for match in matches:
            #Extract the label
            label = re.search(label_pattern, match[0]).group(1).strip()

            #Extract the var if any
            var = re.search(var_pattern, match[0]).group(1).strip()
            if var: 
                var_label_map[var] = label
                    
            #Extract the properties
            properties = set () # To avoid duplicates 
            if match[1] :# this node or rel with label has also poperties inside
                # Remove from the properties anything included in single quotes ' ' or double quoates "" which will be any values (we will avoid : in values that appear in datetimes, since we look for : in property pattern later)
                remove_pattern = r"""(['"][^'"]*['"])"""
                cleared_match = re.sub(remove_pattern, '', match[1])
                properties.update(re.findall(property_pattern,cleared_match ))
                properties = list(properties)
                if properties: #there are properties found for this label
                    label_props_map = PropertiesValidator.__extend_dict_with_list_elements (label_props_map, label, properties)
        return var_label_map, label_props_map
    
    @staticmethod
    def __outside_var_properties_mapping (var_label_map,label_props_map, query):
        ''' 
        Checks in the query if the variables that are mapped with a label (in var_label_map dict) access properties
        outside (in where, return, etc) in format var.property. If they do we update the properties accessed by the
        corresponding label in label_props_map. 
        If we find a variable that accesses a property but we dont have a matching label, we keep this mapping in vars_prop_dict
        (the label of this variable will be inferred)
        Args:
            Dict (var_label_map) that maps any variables with their labels 
            Dict (label_props_map), that maps labels with properties they access
            query (str): The Cypher query to validate.
        Returns:
            Dict (var_label_map) that maps variables with their labels 
            Dict (label_props_map), that maps labels with properties they access,  updated. 
        '''
        var_props_map = {} # The dict that maps variables wih accessed properties
        
        #Find all vars that access a property - Ensure the var pattern is found outside single ('') or double ("") quotes so it is not a value
        # var_property_pattern = r"(?<!')\b(\w+)\s*\.\s*(\w+)\b(?!')" #single quotes only
        var_property_pattern = r'(?<!["\'])\b(\w+)\s*\.\s*(\w+)\b(?!["\'])'

        
        var_props = re.findall(var_property_pattern,query) #each variable matched with its property
        for var_property in var_props:
            variable = var_property [0]
            property = var_property [1]
            if variable in var_label_map: # We know the label of this variable
                label = var_label_map[variable]
                label_props_map = PropertiesValidator.__extend_dict_with_list_elements (label_props_map, label,  [property])
            else: #its a variable that we dont have a matched label (it will be inferred)
                var_props_map = PropertiesValidator.__extend_dict_with_list_elements (var_props_map, variable,  [property])
                    
        return  label_props_map, var_props_map   
       
    @staticmethod
    def __extract_1hop_paths(query):
        ''' From a cypher query extract all the one hop paths and single nodes and return them as a list.
        If any multihop it breaks it into one hop paths

        Args:
            query(str): The query to be validated
        Returns:
            List of one hop paths (including single nodes, if any)
        '''

        # pattern of nodes ((a:Label),(:Label),(a),(a:Label {prop:1}),(:Label {prop:1}),() and Multiple labels using | (e.g., :Label1|Label2))
        # node_pattern = r"\(\s*(?:\s*\w+\s*:\s*\w+\s*|\s*\w*\s*|:\s*\w+\s*|)\s*(?:\{[^}]*\})?\s*\)"#old
        node_pattern = r"\(\s*(?:\s*\w+\s*:\s*\w+(?:\s*\|\s*\w+)*\s*|\s*\w*\s*|:\s*\w+(?:\s*\|\s*\w+)*\s*|)\s*(?:\{[^}]*\})?\s*\)"
        # pattern of relationships
        # rel_pattern = r"\[\s*(?:\s*\w+\s*:\s*\w+\s*|\s*\w*\s*|:\s*\w+\s*|)\s*(?:\{[^}]*\})?\s*\]"#old
        rel_pattern = r"\[\s*(?:\s*\w+\s*:\s*\w+(?:\s*\|\s*\w+)*\s*|\s*\w*\s*|:\s*\w+(?:\s*\|\s*\w+)*\s*|)\s*(?:\{[^}]*\})?\s*\]"
        # combine node and relationships patterns
        path_pattern= rf'({node_pattern}\s*<?-\s*{rel_pattern}\s*->?\s*{node_pattern})'
        # A list containing the extracted paths (converted to one hop paths) and single nodes
        one_hop_paths = []

        #Find the patterns of 1 hop paths in the query 
        matches = re.findall(path_pattern,query,overlapped=True)

        nodes_in_paths = set() #Nodes taht appear in paths
        for path_match in matches:
            one_hop_paths.append(path_match)
            # extract all nodes in the path string
            nodes = re.findall(node_pattern, path_match)
            nodes_in_paths.update(nodes)

        # find all nodes
        all_node_matches = re.findall(node_pattern, query, overlapped=True)
        # filter out nodes that appear in paths
        single_node_matches = [node for node in all_node_matches if node not in nodes_in_paths]

        # Add single nodes to one_hop_paths
        one_hop_paths.extend(single_node_matches)

        return one_hop_paths

    @staticmethod
    def __prepare_query_for_infer (var_label_map, query):
        '''
        1. replace the known vars with their mapped label (so we dont infer them)
        2. Replace -- with -[]-
        3. Remove *x..y in relationships, if any
        4. Break query into one hop paths/ or single nodes
        5. Remove from each 1 hop paths if any properties where accessed
        6. Create a list of 1 hop paths that have unknown variables to infer

        Args:
            Dict (var_label_map): that maps any variables with their labels 
            query(str): The query to be validated
        Returns:
            List of 1 hop paths that have unknown variables to infer 
        '''
        #replace the known vars with their mapped label
        query = replace_with_labels(query, var_label_map)

        # Replace -- with empty relationship
        query = query.replace("--", "-[]-")

        # Remove *x..y in relationships, if any
        query = re.sub(r'\*\s*\d*(?:\s*\.\.\s*\d+)?', '', query)

        #Extract 1 hop paths 
        one_hop_paths = PropertiesValidator.__extract_1hop_paths(query)

        # Remove from each 1 hop paths if any properties where accessed
        # Regular expression to match properties inside curly braces (i.e., { })
        prop_pattern = r"\{[^}]*\}"
        no_prop_paths = [re.sub(prop_pattern, '', path) for path in one_hop_paths]

        # The final list with paths that have unknown variable and will be inferred
        inference_paths = []
        # Define the pattern for detecting unknown variables inside parentheses or square brackets
        pattern = r"\(\w+\)|\[\w+\]"
        # Filter the list to keep only elements that contain unknown variables
        inference_paths = [path for path in no_prop_paths if re.search(pattern, path)]

        return inference_paths