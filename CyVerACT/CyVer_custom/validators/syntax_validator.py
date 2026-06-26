import neo4j
from collections import defaultdict
import regex as re


class SyntaxValidator:
    """
    A class to validate Cypher queries for correct syntax and label consistency.
    """

    def __init__(self, driver , check_multilabeled_nodes=True):
        """
        Initialize the validator with a Neo4j driver.

        Args:
            driver: An instance of the Neo4j driver.
            check_multilabeled_nodes (bool): Whether to check for multilabeled nodes (default: True).

        Raises:
            TypeError: If the driver is not a valid Neo4j driver.
        """
        # Check if driver is an instance of the Neo4j GraphDatabase driver
        if not isinstance(driver, neo4j.Driver):
            raise TypeError("Provided driver is not a valid Neo4j driver (instance of neo4j.Driver).")
        
        self.driver = driver

        # Multilabel nodes
        self.check_multilabeled_nodes = check_multilabeled_nodes
        self.multilabels =  None 

        if  self.check_multilabeled_nodes:
            """Fetch and store multilabeled nodes"""
            rel_query = "MATCH (n) WHERE size(labels(n)) > 1 WITH DISTINCT labels(n) AS labelList RETURN COLLECT(labelList) AS output"
            self.multilabels = self.__read_cypher_query(rel_query)

    def __read_cypher_query(self, query=None, params=None):
        """
        Executes a Cypher query using the instance's driver and query.

        Args:
            query (str, optional): The Cypher query to execute. If not provided, it uses the instance's `query`.
            params (dict, optional): Query parameters. Defaults to None.

        Returns:
            dict: The result of the query execution (assumes a single output).
        """
        with self.driver.session() as session:
            result = session.run(query, parameters=params if params else {})
            return result.single()['output']

    def validate(self,query, database_name=None):
        """
        Checks if the query has correct Cypher syntax.
        It detects these types or errors and warnings:
        - Neo.DatabaseError.Statement.ExecutionFailed: Raised when the database was unable to execute the statement.
        - Neo.ClientError.Statement.SyntaxError: Raised when the provided statement has invalid syntax.
        - Neo.ClientNotification.Statement.ParameterNotProvided: Raised when a parameter is not provided.
        - Neo.ClientNotification.Statement.UnsatisfiableRelationshipTypeExpression: Raised when a relationship type expression cannot possibly be satisfied
        - Neo.ClientError.Statement.ArithmeticError: Raised when an arithmetic error occurs during query execution due to explicit division by zero ("/0", "/0.0" , "/(0)"),
        but not when arithmetic errors may occur at execution time when a divisor becomes zero as part of dynamic execution.
        - Conflicting variables, with the same name but assigned to different labels.

        Args:
            query (str): The Cypher query to validate.
            database_name (str | None) :Database to validate the query against. None (default) uses the database configured on the server side.

        Returns:
            bool: True if the syntax is correct, False otherwise.
            metadata (list[dict]): : A list of dictionaries containing details about notifications, warnings, or errors encountered during validation. 
                Each dictionary includes:  
                - 'code' (str): The error or warning code.  
                - 'description' (str): A detailed message describing the issue.  
        """
        metadata = [] #initialize the list of metadata of errors, warnings or notifications
        # Modify the query to use EXPLAIN for checking the execution plan, whithout executing it 
        explain_query = f"EXPLAIN {query}"

        try:
            records, summary, keys = self.driver.execute_query(explain_query, database_= database_name) #notifications_min_severity='OFF'
            
            #----------Detect specific types of warnings in the query----------------
            if summary.notifications:
                for notification in summary.notifications:
                    if notification['code'] in['Neo.ClientNotification.Statement.ParameterNotProvided', 
                                            'Neo.ClientNotification.Statement.UnsatisfiableRelationshipTypeExpression',
                                            # 'Neo.ClientNotification.Statement.UnknownLabelWarning',
                                            # 'Neo.ClientNotification.Statement.UnknownRelationshipTypeWarning',
                                            # 'Neo.ClientNotification.Statement.UnknownPropertyKeyWarning'
                                            ]: 
                        metadata.append({'code': notification['code'], 'description': notification['description']})
                                            
           
            #----------Detect arithmetic errors of explicit division by zero ----------------
            # that will result in Neo.ClientError.Statement.ArithmeticError in execution
            # but not arithmetic errors that may occur due to a divisor becoming zero at execution time
            # Regex pattern to catch explicit " / 0", " / 0.0", or " / (0)"
            divisor_zero_pattern = r'/\s*(?:\(\s*0(?:\.0*)?\s*\)|0(?:\.0*)?)\s*(?![\w(])'
            if re.search(divisor_zero_pattern, query):
                metadata.append({'code':'Neo.ClientError.Statement.ArithmeticError', 'description': 'Division by zero.'})
                
            
            #----------Detect conflicting labels----------------
            
            # Find nodes or rels with label (even if they are followed by property access in {})
            matches = re.findall(r"[\(\[](\s*\w+\s*):(\s*\w+\s*)(?:\s*\{[^\}]*\})?[\)\]]", query)
                                
            # Dictionary to store variables and their associated labels
            variable_labels = defaultdict(set)  # initializes each key with an empty set
    
            # Populate the dictionary with variables and corresponding labels
            for var, label in matches:
                variable_labels[var.strip()].add(label.strip())
            # Find conflicting variables
            # Conflicting variables are considered if they have the same variable name but different labels 
            # and the labels are not part of the multilabels (if multilabels check is True)
            if self.check_multilabeled_nodes:
                # When checking for multilabeled nodes, only consider conflicting variables that are not part of multilabels
                conflicting_vars = {
                    var: labels
                    for var, labels in variable_labels.items()
                    if len(labels) > 1 and not self.__subset_in_multilabels(labels, self.multilabels)
                }
            else:
                # If not checking multilabeled nodes, just consider conflicting variables that have multiple labels
                conflicting_vars = {
                    var: labels
                    for var, labels in variable_labels.items()
                    if len(labels) > 1
                }

            # If conflicting variables exist, raise an error
            error_messages = []
            if conflicting_vars:
                for var, labels in conflicting_vars.items():
                    # print(f"Variable '{var}' has conflicting labels: {', '.join(labels)}")
                    error_messages.append(f"Variable '{var}' has conflicting labels: {', '.join(labels)}")
                if len(error_messages)==1:
                    concatenated_error_message = error_messages[0]
                else:
                    concatenated_error_message = " and ".join(error_messages)
                metadata.append({'code': 'ConflictingVariablesError', 'description': concatenated_error_message})
                
            
            if metadata:
                return False , metadata
            
            return True, metadata
        except Exception as e:
            # Detects:
            # -Neo.DatabaseError.Statement.ExecutionFailed
            # -Neo.ClientError.Statement.SyntaxError

            #Remove the test query from the metadata, starting with "EXPLAIN ...
            if "EXPLAIN" in e.message:
                metadata_text = e.message.split("EXPLAIN")[0].strip('"')
            else:
                metadata_text = e.message
            
            metadata.append({'code': e.code, 'description': metadata_text})
            return False, metadata

    # This method does not require access to any instance or class data. It is  purely a utility function that performs an operation (addition) and 
    # returns the result. Static methods are typically used when the method does not need to modify or access the object's state.
    @staticmethod
    def __subset_in_multilabels(subset, list_of_lists):
        """
        Check if a subset exists within a list of lists.

        Args:
            subset (list): The subset to search for.
            list_of_lists (list): A list of lists to search within.

        Returns:
            bool: True if the subset is found in any inner list, False otherwise.
        """
        for inner_list in list_of_lists:
            # Check if `subset` is a subset of `inner_list`
            if all(item in inner_list for item in subset):
                return True
        return False