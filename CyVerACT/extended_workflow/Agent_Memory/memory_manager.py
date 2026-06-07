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

    def check_episodic_memory(self, question: str, embedder) -> str:
        """
        Looks up if an identical or highly similar question was already solved.
        Returns the correct Cypher query string if found, otherwise returns None.
        """
        question_vector = embedder.embed_query(question)

        query = """
        CALL db.index.vector.queryNodes('question_embeddings', 1, $question_vector)
        YIELD node AS closest_question, score
        MATCH (closest_question)-[:RESOLVED_WITH]->(a:Answer)
        RETURN a.cypher AS cypher, score
        """

        with self.driver.session() as session:
            result = session.run(query, {"question_vector": question_vector})
            records = list(result)

            if records:
                match = records[0]
                if match["score"] > 0.99:
                    return match["cypher"]

        return None

    def store_attempt(self, question: str, cypher: str, raw_errors: list, attempt_num: int, embedder):
        """Stores evaluation attempts into the graph trajectory."""

        success = len(raw_errors) == 0
        errors_data = []

        for err in raw_errors:
            raw_code = err.get('code', 'ExecutionFailed')
            exact_error_type = raw_code.split('.')[-1]
            exact_message = err.get('description', '')

            # -----------------------------
            # CypherError embedding
            # -----------------------------
            semantic_error = f"{exact_error_type}: {exact_message}"
            error_vector = embedder.embed_query(semantic_error)

            errors_data.append({
                "raw_message": exact_message,
                "error_type": exact_error_type,
                "vector": error_vector   
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

        CREATE (e:CypherError {
            message: err.raw_message,
            embedding: err.vector
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

    def get_fix_rules_vector_search(self, string_errors: list, embedder) -> list:
        """
        Retrieves rules using Hybrid Search (WRRF):
        Combines Semantic Vector Search with BM25 Keyword Search.
        Merges results using Weighted Reciprocal Rank Fusion.
        """
        import re
        if not string_errors:
            return []

        combined_feedback = []

        with self.driver.session() as session:
            for err_string in string_errors:

                parts = err_string.split(':', 1)
                raw_code = parts[0].strip()
                exact_error_type = raw_code.split('.')[-1] if '.' in raw_code else raw_code
                raw_message = parts[1].strip() if len(parts) > 1 else err_string

                error_vector = embedder.embed_query(raw_message)

                vector_query = """
                CALL db.index.vector.queryNodes('error_embeddings', 10, $error_vector)
                YIELD node AS error_type_node, score
                WHERE error_type_node.name = $exact_error_type
                MATCH (error_type_node)-[:FIXED_WITH]->(fr:FixRule)
                RETURN DISTINCT fr.rule AS instruction
                LIMIT 10
                """

                vec_result = session.run(vector_query, {
                    "error_vector": error_vector,
                    "exact_error_type": exact_error_type
                })

                vector_hits = [record["instruction"] for record in vec_result]

                safe_keywords = re.sub(r'[^\w\s]', ' ', raw_message).split()
                ft_query_string = " OR ".join([word for word in safe_keywords if len(word) > 2])

                kw_hits = []

                if ft_query_string:
                    keyword_query = """
                    CALL db.index.fulltext.queryNodes('fixrule_text', $ft_query_string)
                    YIELD node AS fr, score
                    RETURN DISTINCT fr.rule AS instruction
                    LIMIT 10
                    """

                    try:
                        kw_result = session.run(keyword_query, {
                            "ft_query_string": ft_query_string
                        })
                        kw_hits = [record["instruction"] for record in kw_result]
                    except Exception as e:
                        print(f"Keyword search bypassed: {e}")

                rrf_scores = {}
                k_constant = 60

                for rank, instruction in enumerate(vector_hits):
                    rrf_scores[instruction] = rrf_scores.get(instruction, 0.0) + (1.0 / (k_constant + rank))

                for rank, instruction in enumerate(kw_hits):
                    rrf_scores[instruction] = rrf_scores.get(instruction, 0.0) + (1.5 / (k_constant + rank))

                sorted_rules = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
                top_1_rules = sorted_rules[:1]

                if top_1_rules:
                    feedback_str_parts = []
                    for i, (instruction, _) in enumerate(top_1_rules):
                        feedback_str_parts.append(f"   - Rule {i+1}: {instruction}")

                    combined_rules = "\n".join(feedback_str_parts)

                    feedback_str = (
                        f"General Rules to Consider:\n{combined_rules}\n"
                        f"Specific Fix Required: Address this engine feedback -> '{raw_message}'"
                    )

                    combined_feedback.append(feedback_str)

                else:
                    combined_feedback.append(
                        f"Specific Fix Required: Address this engine feedback -> '{raw_message}'"
                    )

        return combined_feedback