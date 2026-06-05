from neo4j import Driver

class MemoryManager:
    def __init__(self, driver: Driver):
        self.driver = driver

    def init_question(self, question: str):
        """Creates the Question node at the very beginning of the pipeline (cypher_generator)"""
        query = """
        MERGE (q:Question {text: $question})
        """
        with self.driver.session() as session:
            session.run(query, {"question": question})

    def store_successful_answer(self, question: str, final_cypher: str, records_found: int):
        """Links the Question to the final successful Answer upon execution (cypher_executor)"""
        query = """
        MATCH (q:Question {text: $question})
        MERGE (a:Answer {cypher: $final_cypher})
        ON CREATE SET a.records_found = $records_found
        MERGE (q)-[:RESOLVED_WITH]->(a)
        """
        with self.driver.session() as session:
            session.run(query, {
                "question": question,
                "final_cypher": final_cypher,
                "records_found": records_found
            })

    def store_attempt(self, question: str, cypher: str, raw_errors: list, attempt_num: int):
        """
        Stores the evaluation attempt in Neo4j
        raw_errors should be a list of dicts directly from the validators
        """
        success = len(raw_errors) == 0
        errors_data = []

        for err in raw_errors:
            # Raw code from the validator (e.g., "Neo.ClientError.Statement.SyntaxError")
            raw_code = err.get('code', 'ExecutionFailed') 
            
            # Cleaning it to match the exact ErrorType node name (e.g., "SyntaxError")
            exact_error_type = raw_code.split('.')[-1]
            
            exact_message = err.get('description', '')
            
            errors_data.append({
                "raw_message": exact_message, 
                "error_type": exact_error_type 
            })

        query = """
        MERGE (q:Question {text: $question})
        CREATE (a:Attempt {
            attempt_num: $attempt_num,
            cypher: $cypher,
            success: $success
        })
        CREATE (q)-[:HAS_ATTEMPT]->(a)
        
        WITH a, $errors_data AS errors
        UNWIND errors AS err
        CREATE (e:CypherError {message: err.raw_message})
        CREATE (a)-[:CAUSED_ERROR]->(e)
        
        WITH e, err
        MATCH (et:ErrorType {name: err.error_type})
        CREATE (e)-[:HAS_ERROR_TYPE]->(et)
        """
        
        with self.driver.session() as session:
            session.run(query, {
                "question": question,
                "cypher": cypher,
                "success": success,
                "attempt_num": attempt_num,
                "errors_data": errors_data
            })
            
    def get_fix_rules_for_errors(self, string_errors: list) -> list:
        """
        Retrieves generic rules from the DB and combines them with specific runtime errors
        """
        if not string_errors:
            return []

        combined_feedback = []

        with self.driver.session() as session:
            for err_string in string_errors:
                # Separating the raw code from the specific Neo4j engine message
                parts = err_string.split(':', 1)
                raw_code = parts[0].strip()
                raw_message = parts[1].strip() if len(parts) > 1 else err_string
                
                # Extracting the generic ErrorType to query the database
                # Example: "Neo.ClientError.Statement.SyntaxError" -> "SyntaxError"
                generic_error_type = raw_code.split('.')[-1] 

                # Query the DB for the broad architectural rule
                query = """
                MATCH (et:ErrorType {name: $error_type})-[:FIXED_WITH]->(fr:FixRule)
                RETURN fr.rule AS instruction
                """
                result = session.run(query, {"error_type": generic_error_type})
                records = list(result)

                # Specific + Generic feedback
                if records:
                    generic_rule = records[0]["instruction"]
                    feedback_str = (
                        f"General Rule to Apply: {generic_rule}\n"
                        f"Specific Fix Required: Address this engine feedback -> '{raw_message}'"
                    )
                    combined_feedback.append(feedback_str)
                else:
                    # Fallback if the error isn't mapped in the DB (impossible but whatev)
                    combined_feedback.append(f"Specific Fix Required: Address this engine feedback -> '{raw_message}'")

        return combined_feedback