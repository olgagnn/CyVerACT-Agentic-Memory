from neo4j import Driver

class MemoryManager:
    def __init__(self, driver: Driver):
        self.driver = driver

    def init_question(self, question: str):
        """Creates the Question node at the beginning of the pipeline."""
        query = """
        MERGE (q:Question {text: $question})
        """
        with self.driver.session() as session:
            session.run(query, {"question": question})

    def store_successful_answer(self, question: str, final_cypher: str, records_found: int, embedder):
        """Links the Question to the successful Answer and saves the Question vector embedding."""
        question_vector = embedder.embed_query(question)
        
        query = """
        MERGE (q:Question {text: $question})
        SET q.embedding = $vector
        MERGE (a:Answer {cypher: $final_cypher})
        ON CREATE SET a.records_found = $records_found
        MERGE (q)-[:RESOLVED_WITH]->(a)
        """
        with self.driver.session() as session:
            session.run(query, {
                "question": question,
                "final_cypher": final_cypher,
                "records_found": records_found,
                "vector": question_vector
            })

    def check_episodic_memory(self, question: str, embedder) -> dict:
        """
        Retrieves a structurally similar previously solved question using a Two-Tier system.
        Returns a dictionary with the tier, cypher, and score, or None if below threshold.
        """
        question_vector = embedder.embed_query(question)
        
        query = """
        CALL db.index.vector.queryNodes('question_embeddings', 1, $question_vector)
        YIELD node AS closest_question, score
        MATCH (closest_question)-[:RESOLVED_WITH]->(a:Answer)
        RETURN closest_question.text AS previous_question,
               a.cypher AS cypher,
               score
        ORDER BY score DESC
        LIMIT 1
        """
        with self.driver.session() as session:
            result = session.run(query, {"question_vector": question_vector})
            record = result.single()

            if record:
                score = record["score"]
                
                print("\n=== Pre-Generation Episodic Check ===")
                print(f"Matched Question: {record['previous_question']}")
                print(f"Similarity Score: {score:.4f}")
                
                # Tier 1: Near-Exact Match
                if score >= 0.95:
                    print("Classification: TIER 1 (Near-Exact Match)\n")
                    print(f"Retrieved Cypher: {record['cypher']}\n")
                    return {
                        "tier": "exact",
                        "cypher": record["cypher"],
                        "score": score
                    }
                
                # Tier 2: Structural Reference (Threshold lowered to 0.80 to capture entity swaps)
                elif score >= 0.80:
                    print("Classification: TIER 2 (Structural Reference)\n")
                    print(f"Retrieved Cypher: {record['cypher']}\n") 
                    return {
                        "tier": "structural",
                        "cypher": record["cypher"],
                        "score": score
                    }
                
                else:
                    print("Classification: BELOW THRESHOLD (No memory injected)\n")

        return None

    def store_attempt(self, question: str, cypher: str, raw_errors: list, attempt_num: int, embedder):
        """Stores evaluation attempts with SPLIT embeddings for better retrieval."""
        success = len(raw_errors) == 0
        errors_data = []

        for err in raw_errors:
            raw_code = err.get('code', 'ExecutionFailed')
            exact_error_type = raw_code.split('.')[-1]
            exact_message = err.get('description', '')

            # 1. Error Vector (Strictly captures the database failure)
            error_semantic = f"{exact_error_type}: {exact_message}"
            error_vector = embedder.embed_query(error_semantic)

            # 2. Trajectory Vector (Strictly captures the structural intent)
            trajectory_semantic = f"Goal: {question} | Cypher: {cypher} | Error: {exact_message}"
            trajectory_vector = embedder.embed_query(trajectory_semantic)

            errors_data.append({
                "raw_message": exact_message,
                "error_type": exact_error_type,
                "error_vector": error_vector,
                "trajectory_vector": trajectory_vector
            })

        query = """
        MERGE (q:Question {text: $question})
        CREATE (a:Attempt {attempt_num: $attempt_num, cypher: $cypher, success: $success})
        CREATE (q)-[:HAS_ATTEMPT]->(a)
        
        WITH a, $errors_data AS errors
        UNWIND errors AS err
        
        CREATE (e:CypherError {
            message: err.raw_message,
            error_embedding: err.error_vector,
            trajectory_embedding: err.trajectory_vector
        })
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

    def get_trajectory_fix_context(self, current_question: str, failed_cypher: str, raw_error_message: str, embedder, limit: int = 3) -> str:
        """Retrieves trajectories using a weighted combination of Error Similarity (70%) and Trajectory Similarity (30%)."""
        
        error_semantic = raw_error_message 
        trajectory_semantic = f"Goal: {current_question} | Cypher: {failed_cypher} | Error: {raw_error_message}"
        
        error_target_vector = embedder.embed_query(error_semantic)
        trajectory_target_vector = embedder.embed_query(trajectory_semantic)

        # Native Neo4j weighted vector retrieval
        query = """
        CALL db.index.vector.queryNodes('error_vector_embeddings', $search_limit, $error_target_vector)
        YIELD node AS error_node, score AS err_score
        
        MATCH (a:Attempt)-[:CAUSED_ERROR]->(error_node)
        MATCH (q:Question)-[:HAS_ATTEMPT]->(a)
        MATCH (q)-[:RESOLVED_WITH]->(ans:Answer)
        
        // Calculate the trajectory similarity using native cosine similarity function
        WITH q, a, error_node, ans, err_score,
             vector.similarity.cosine(error_node.trajectory_embedding, $trajectory_target_vector) AS traj_score
             
        // Apply your 70/30 weighting
        WITH q, a, error_node, ans, err_score, traj_score,
             (0.7 * err_score) + (0.3 * traj_score) AS combined_score
        ORDER BY combined_score DESC
        
        RETURN 
            q.text AS past_question, 
            a.cypher AS failed_cypher, 
            error_node.message AS error_message, 
            ans.cypher AS fixed_cypher, 
            combined_score
        """

        context_blocks = []
        seen_errors = set()

        with self.driver.session() as session:
            result = session.run(query, {
                "error_target_vector": error_target_vector, 
                "trajectory_target_vector": trajectory_target_vector,
                "search_limit": limit * 3 
            })

            for record in result:
                combined_score = record['combined_score']
                
                # 1. GARBAGE FILTER THRESHOLD
                if combined_score < 0.80:
                    continue
                
                # 2. STRONG DEDUPLICATION (Groups similar syntax errors regardless of line numbers)
                error_signature = record['error_message'].split(":")[0].strip()
                if error_signature in seen_errors:
                    continue 
                
                seen_errors.add(error_signature)

                # 3. COGNITIVE FORCE PROMPT
                block = (
                    f"--- Trajectory Strategy (Relevance: {combined_score:.2f}) ---\n"
                    f"Past Intent: {record['past_question']}\n"
                    f"Past Failure: {record['failed_cypher']}\n"
                    f"Resulting Engine Error: {record['error_message']}\n"
                    f"Successful Structural Fix: {record['fixed_cypher']}\n"
                    f"CRITICAL INSTRUCTION: Analyze how the 'Successful Structural Fix' altered the syntax of the 'Past Failure' to resolve the engine error. Apply this exact same structural transformation to your current failing query.\n"
                )
                context_blocks.append(block)
                
                if len(context_blocks) >= limit:
                    break

        return "\n".join(context_blocks)

    def get_fix_rules(self, string_errors: list) -> list:
        """
        Retrieve generic repair rules using exact ErrorType matching.
        """
        if not string_errors:
            return []

        rules = []

        with self.driver.session() as session:
            for err in string_errors:
                # Isolate the exact Neo4j Error code (e.g., 'SyntaxError')
                raw_code = err.split(":")[0].strip()
                error_type = raw_code.split(".")[-1]

                query = """
                MATCH (et:ErrorType {name:$error_type})-[:FIXED_WITH]->(fr:FixRule)
                RETURN fr.rule AS rule
                """

                result = session.run(
                    query,
                    {"error_type": error_type}
                )

                rules.extend(
                    [record["rule"] for record in result]
                )

        # Return list with duplicates removed
        return list(dict.fromkeys(rules))
