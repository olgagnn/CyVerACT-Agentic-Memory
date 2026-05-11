from neo4j import GraphDatabase
from fastembed import TextEmbedding

class CyVerMemory:
    def __init__(self, uri, user, password, database="neo4j"):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.database = database
        self.embedding_model = TextEmbedding(
            model_name="BAAI/bge-small-en-v1.5",
            cache_dir="./fastembed_cache"
        )

    def close(self):
        self.driver.close()

    def add_episodic_memory(self, user_id, session_id, user_question, agent_answer):

        cypher = """
        MERGE (u:User {user_id: $user_id})
        MERGE (s:Session {session_id: $session_id})
        MERGE (u)-[:PARTICIPATES_IN]->(s)

        OPTIONAL MATCH (s)-[:HAS_EPISODE]->(last:Episode)
        WHERE NOT (last)-[:NEXT_EPISODE]->()

        CREATE (e:Episode {
            user_question: $user_question,
            agent_answer: $agent_answer,
            timestamp: datetime()
        })

        MERGE (s)-[:HAS_EPISODE]->(e)

        WITH last, e
        WHERE last IS NOT NULL
        MERGE (last)-[:NEXT_EPISODE]->(e)
        """

        with self.driver.session(database=self.database) as session:
            session.run(
                cypher,
                user_id=user_id,
                session_id=session_id,
                user_question=user_question,
                agent_answer=agent_answer
            )

    def add_procedural_error(
        self,
        session_id,
        wrong_cypher,
        error_type,
        error_msg,
        fix_rule,
        attempt_num=1
    ):

        cypher = """
        MATCH (s:Session {session_id: $session_id})-[:HAS_EPISODE]->(e:Episode)
        WHERE NOT (e)-[:NEXT_EPISODE]->()

        CREATE (c:CypherCandidate {
            query_string: $wrong_cypher,
            attempt: $attempt_num,
            status: "Failed"
        })

        CREATE (err:ExecutionError {
            error_type: $error_type,
            error_message: $error_msg
        })

        CREATE (r:FixRule {
            rule_description: $fix_rule
        })

        MERGE (e)-[:GENERATED]->(c)
        MERGE (c)-[:RESULTED_IN]->(err)
        MERGE (err)-[:TAUGHT_LESSON]->(r)
        """

        #embedding_vector = list(self.embedding_model.embed([fix_rule]))[0].tolist()

        with self.driver.session(database=self.database) as session:
            session.run(
                cypher,
                session_id=session_id,
                wrong_cypher=wrong_cypher,
                error_type=error_type,
                error_msg=error_msg,
                fix_rule=fix_rule,
                attempt_num=attempt_num,
                #embedding=embedding_vector
            )

    def retrieve_context(self, session_id, current_question):

        cypher = """
        OPTIONAL MATCH (s:Session {session_id: $session_id})-[:HAS_EPISODE]->(e:Episode)
        WITH e ORDER BY e.timestamp DESC LIMIT 3

        WITH collect({
            question: e.user_question,
            answer: e.agent_answer
        }) AS chat_history

        CALL db.index.vector.queryNodes(
            'rule_embedding',
            2,
            $question_embedding
        )
        YIELD node AS rule, score

        WHERE score > 0.7

        RETURN
            chat_history,
            collect({
                rule: rule.rule_description,
                relevance_score: score
            }) AS relevant_rules
        """

        question_embedding = list(
            self.embedding_model.embed([current_question])
        )[0].tolist()

        with self.driver.session(database=self.database) as session:
            result = session.run(
                cypher,
                session_id=session_id,
                question_embedding=question_embedding
            )

            record = result.single()

            return {
                "chat_history": record["chat_history"] if record else [],
                "procedural_rules": record["relevant_rules"] if record else []
            }