from neo4j_graphrag.schema import  format_schema

#------------NEO4J code---------------------------------
import neo4j
from neo4j import Query
from typing import Any,  Optional, Dict, List
from neo4j.exceptions import ClientError

BASE_KG_BUILDER_LABEL = "__KGBuilder__"
BASE_ENTITY_LABEL = "__Entity__"
EXCLUDED_LABELS = ["_Bloom_Perspective_", "_Bloom_Scene_"]
EXCLUDED_RELS = ["_Bloom_HAS_SCENE_"]
EXHAUSTIVE_SEARCH_LIMIT = 10000
LIST_LIMIT = 128
DISTINCT_VALUE_LIMIT = 10

NODE_PROPERTIES_QUERY = (
    "CALL apoc.meta.data({sample:-1}) "
    "YIELD label, other, elementType, type, property "
    "WHERE NOT type = 'RELATIONSHIP' AND elementType = 'node' "
    "AND NOT label IN $EXCLUDED_LABELS "
    "WITH label AS nodeLabel, collect({property:property, type:type}) AS properties "
    "RETURN {label: nodeLabel, properties: properties} AS output"
)

REL_PROPERTIES_QUERY = (
    "CALL apoc.meta.data({sample:-1}) "
    "YIELD label, other, elementType, type, property "
    "WHERE NOT type = 'RELATIONSHIP' AND elementType = 'relationship' "
    "AND NOT label in $EXCLUDED_LABELS "
    "WITH label AS relType, collect({property:property, type:type}) AS properties "
    "RETURN {type: relType, properties: properties} AS output"
)

REL_QUERY = (
    "CALL apoc.meta.data({sample:-1}) "
    "YIELD label, other, elementType, type, property "
    "WHERE type = 'RELATIONSHIP' AND elementType = 'node' "
    "UNWIND other AS other_node "
    "WITH * WHERE NOT label IN $EXCLUDED_LABELS "
    "AND NOT other_node IN $EXCLUDED_LABELS "
    "RETURN {start: label, type: property, end: toString(other_node)} AS output"
)

INDEX_QUERY = (
    "CALL apoc.schema.nodes() YIELD label, properties, type, size, valuesSelectivity "
    "WHERE type = 'RANGE' RETURN *, "
    "size * valuesSelectivity as distinctValues"
)
def _value_sanitize(d: Any) -> Any:
    """Sanitize the input dictionary or list.

    Sanitizes the input by removing embedding-like values,
    lists with more than 128 elements, that are mostly irrelevant for
    generating answers in a LLM context. These properties, if left in
    results, can occupy significant context space and detract from
    the LLM's performance by introducing unnecessary noise and cost.

    Args:
        d (Any): The input dictionary or list to sanitize.

    Returns:
        Any: The sanitized dictionary or list.
    """
    if isinstance(d, dict):
        new_dict = {}
        for key, value in d.items():
            if isinstance(value, dict):
                sanitized_value = _value_sanitize(value)
                if (
                    sanitized_value is not None
                ):  # Check if the sanitized value is not None
                    new_dict[key] = sanitized_value
            elif isinstance(value, list):
                if len(value) < LIST_LIMIT:
                    sanitized_value = _value_sanitize(value)
                    if (
                        sanitized_value is not None
                    ):  # Check if the sanitized value is not None
                        new_dict[key] = sanitized_value
                # Do not include the key if the list is oversized
            else:
                new_dict[key] = value
        return new_dict
    elif isinstance(d, list):
        if len(d) < LIST_LIMIT:
            return [
                _value_sanitize(item) for item in d if _value_sanitize(item) is not None
            ]
        else:
            return None
    else:
        return d
def query_database(
    driver: neo4j.Driver,
    query: str,
    params: Dict[str, Any] = {},
    session_params: Dict[str, Any] = {},
    database: Optional[str] = None,
    timeout: Optional[float] = None,
    sanitize: bool = False,
) -> List[Dict[str, Any]]:
    """
    Queries the database.

    Args:
        driver (neo4j.Driver):  Neo4j Python driver instance.
        query (str): The cypher query.
        params (Optional[dict[str, Any]]): The query parameters. Defaults to None.
        session_params (Optional[dict[str, Any]]): Parameters to pass to the
            session used for executing the query. Defaults to None.
        database (Optional[str]): The name of the database to connect to. Default is 'neo4j'.
        timeout (Optional[float]): The timeout for transactions in seconds.
                Useful for terminating long-running queries.
                By default, there is no timeout set.
        sanitize (bool): A flag to indicate whether to remove lists with
                more than 128 elements from results. Useful for removing
                embedding-like properties from database responses. Default is False.

    Returns:
        list[dict[str, Any]]: the result of the query in json format.
    """
    if not session_params:
        data = driver.execute_query(
            Query(text=query, timeout=timeout),
            database_=database,
            parameters_=params,
        )
        json_data = [r.data() for r in data.records]
        if sanitize:
            json_data = [_value_sanitize(el) for el in json_data]
        return json_data

    session_params.setdefault("database", database)
    with driver.session(**session_params) as session:
        result = session.run(Query(text=query, timeout=timeout), params)
        json_data = [r.data() for r in result]
        if sanitize:
            json_data = [_value_sanitize(el) for el in json_data]
        return json_data

def get_structured_schema_custom(
    driver: neo4j.Driver,
    is_enhanced: bool = False,
    database: Optional[str] = None,
    timeout: Optional[float] = None,
    sanitize: bool = False,
) -> dict[str, Any]:
    """
    Returns the structured schema of the graph.

    Returns a dict with following format:

    .. code:: python

        {
            'node_props': {
                'Person': [{'property': 'id', 'type': 'INTEGER'}, {'property': 'name', 'type': 'STRING'}]
            },
            'rel_props': {
                'KNOWS': [{'property': 'fromDate', 'type': 'DATE'}]
            },
            'relationships': [
                {'start': 'Person', 'type': 'KNOWS', 'end': 'Person'}
            ],
            'metadata': {
                'constraint': [
                    {'id': 7, 'name': 'person_id', 'type': 'UNIQUENESS', 'entityType': 'NODE', 'labelsOrTypes': ['Person'], 'properties': ['id'], 'ownedIndex': 'person_id', 'propertyType': None},
                ],
                'index': [
                    {'label': 'Person', 'properties': ['name'], 'size': 2, 'type': 'RANGE', 'valuesSelectivity': 1.0, 'distinctValues': 2.0},
                ]
            }
        }

    Note:
        The internal structure of the returned dict depends on the apoc.meta.data
        and apoc.schema.nodes procedures.

    Warning:
        Some labels are excluded from the output schema:

        - The `__Entity__` and `__KGBuilder__` node labels which are created by the KG Builder pipeline within this package
        - Some labels related to Bloom internals.

    Args:
        driver (neo4j.Driver): Neo4j Python driver instance.
        is_enhanced (bool): Flag indicating whether to format the schema with
            detailed statistics (True) or in a simpler overview format (False).
        database (Optional[str]): The name of the database to connect to. Default is 'neo4j'.
        timeout (Optional[float]): The timeout for transactions in seconds.
            Useful for terminating long-running queries.
            By default, there is no timeout set.
        sanitize (bool): A flag to indicate whether to remove lists with
            more than 128 elements from results. Useful for removing
            embedding-like properties from database responses. Default is False.

    Returns:
        dict[str, Any]: the graph schema information in a structured format.
    """
    node_properties = [
        data["output"]
        for data in query_database(
            driver=driver,
            query=NODE_PROPERTIES_QUERY,
            params={
                "EXCLUDED_LABELS": EXCLUDED_LABELS
                + [BASE_ENTITY_LABEL, BASE_KG_BUILDER_LABEL]
            },
            database=database,
            timeout=timeout,
            sanitize=sanitize,
        )
    ]

    rel_properties = [
        data["output"]
        for data in query_database(
            driver=driver,
            query=REL_PROPERTIES_QUERY,
            params={"EXCLUDED_LABELS": EXCLUDED_RELS},
            database=database,
            timeout=timeout,
            sanitize=sanitize,
        )
    ]

    relationships = [
        data["output"]
        for data in query_database(
            driver=driver,
            query=REL_QUERY,
            params={
                "EXCLUDED_LABELS": EXCLUDED_LABELS
                + [BASE_ENTITY_LABEL, BASE_KG_BUILDER_LABEL]
            },
            database=database,
            timeout=timeout,
            sanitize=sanitize,
        )
    ]

    # Get constraints and indexes
    try:
        constraint = query_database(
            driver=driver,
            query="SHOW CONSTRAINTS",
            database=database,
            timeout=timeout,
            sanitize=sanitize,
        )
        index = query_database(
            driver=driver,
            query=INDEX_QUERY,
            database=database,
            timeout=timeout,
            sanitize=sanitize,
        )
    except ClientError:
        constraint = []
        index = []

    structured_schema = {
        "node_props": {el["label"]: el["properties"] for el in node_properties},
        "rel_props": {el["type"]: el["properties"] for el in rel_properties},
        "relationships": relationships,
        "metadata": {"constraint": constraint, "index": index},
    }
    return structured_schema

#---------------------------------------------------------
# ---------------------------------------------------------
def get_rel_properties(driver, database_name, source_node, rel, target_node, structured_schema):
    ''' 
    Based on a source and a target node and the rel between them, 
    get the properties (if any) of the relationship  in this path.

    driver: the neo4j driver of the KG database
    database_name(str): the database name
    source_node (str): node label of source node
    rel (str) : rel type
    target_node (str): node label of target node
    structured_schema(dict): the structured schema of the KG 

    Returns in a structured format of a dict the rel type with its properties
    e.g., 
     {'<REL>' : [{'property': '<property_name>', 'type': '<PROPERTY_TYPE>'}]}
    '''

    #Check if the relationship has properties and get the properties from a query
    query = f"""
    MATCH (s:{source_node})-[r:{rel}]->(t:{target_node})
    RETURN keys(r)  as properties LIMIT 1
    """
    # Execute the dynamic query
    result = driver.execute_query(query, database_= database_name)
    rel_properties = result[0][0]['properties']
    structured_dict = {}
    props_with_types = []# list of property names and types  [{'property': '<property_name>', 'type': '<PROPERTY_TYPE>'}]}
    if rel_properties:
        #Get all the properties of this rel with their types 
        all_rel_properties = structured_schema['rel_props'][rel]
        #keep only those that appear in this defined one-hop path
        for property in rel_properties:
            for enhanced_prop in all_rel_properties:
                if enhanced_prop['property'] == property:
                    props_with_types.append({'property':property, 'type':enhanced_prop['type'] })
                    break
        
        structured_dict[rel] = props_with_types

    else:
        structured_dict[rel] = rel_properties

    return structured_dict

def format_structured(label, properties):
    '''
    Format the structured format of a label with its properties list (with types of properties) 
    to a human-readable string. 

    Parameters:
        label (str): The label of the node or the type of the relationship.
        properties (list): A list of the properties with their types, 
                           e.g., [{'property': '<property_name>', 'type': '<PROPERTY_TYPE>'}]
    
    Returns:
        str: A single string in the format 'LABEL {property_name: PROPERTY_TYPE, ...}'
    '''
    if properties:
        props_str = ', '.join(f"{prop['property']}: {prop['type']}" for prop in properties)
        return f"{label} {{{props_str}}}"
    else:
        return f"{label}"

def format_final_schema(driver, database_name, structured_schema, original_structured_schema, inline_props=True):
    ''' 
    Format the structured schema from a dictionary into a human-readable string.
    The structured_schema may be the same as or a filtered version of the original_structured_schema.

    Parameters:
        driver: the neo4j driver of the KG database
        database_name(str): the database name
        structured_schema (dict): The structured schema (filtered or full), with node labels, their properties,
                                  relationship types, and one-hop paths.
        original_structured_schema (dict): The original, full structured schema containing all nodes, relationships,
                                           properties, and one-hop paths.
        inline_props (bool): If True, includes property types inline within one-hop path descriptions. 
                             If False, lists the node/rel definitions separately.

    Returns:
        str: A human-readable string describing the schema.

    Example:

        structured_schema = {
            'node_props': {
                '<Node>': [{'property': '<property_name>', 'type': '<PROPERTY_TYPE>'}]
            },
            'rel_props': {
                '<REL>' : [{'property': '<property_name>', 'type': '<PROPERTY_TYPE>'}]
            'relationships': [
                {'start': '<Node>', 'type': '<REL>', 'end': '<Node>'},
            ]
        }

    Output (if inline_props=True):
        Nodes properties: 
        <NODE> {<property_name>: <PROPERTY_TYPE>}
        Relationship properties:
        <REL> {<property_name>: <PROPERTY_TYPE>}
        The relationships:
        (<NODE>)-[<REL>]-(<NODE>)
        

    Output (if inline_props=False):
        Nodes properties: 
        <NODE> {<property_name>: <PROPERTY_TYPE>}
        Relationship properties:
        <REL> {<property_name>: <PROPERTY_TYPE>}
        The relationships:
        (<NODE> {<property_name>: <PROPERTY_TYPE>})-[<REL> {<property_name>: <PROPERTY_TYPE>}]->(<NODE> {<property_name>: <PROPERTY_TYPE>})
    '''

    if inline_props:
        # A list of all the node labels in the given KG schema with their properties and the type of properties
        node_properties_types = [] 
        # A list of all the relationship type in the given KG schema with their properties and the type of properties
        rel_properties_types = []
        # A list of all the one hop paths in the given KG schema with properties in nodes and rels
        paths_nodes_rels_properties_types = []

        for node_label, properties in structured_schema['node_props'].items():
            node_properties_types.append(format_structured(node_label, properties))
        
        for rel_type, properties in structured_schema['rel_props'].items():
            rel_properties_types.append(format_structured(rel_type, properties))
        
        for path in structured_schema['relationships']:
            #add in the nodes of the path their properties,and in the rel of the path only the properties that apply to this path
            source_node = path['start'] 
            rel = path['type']
            target_node = path['end']

            source_node_props = format_structured(source_node, original_structured_schema['node_props'].get(source_node, [])) #get properties of the source node if any
            target_node_props = format_structured(target_node, original_structured_schema['node_props'].get(target_node, []))#get properties of the target node if any
            rel_props_dict = get_rel_properties(driver, database_name, source_node, rel, target_node, original_structured_schema)
            rel_props = format_structured(rel, rel_props_dict[rel])
            paths_nodes_rels_properties_types.append('(:'+source_node_props +')'+ '-[:'+ rel_props + ']->' + '(:'+target_node_props+')')
         

        filtered_schema = 'Node properties:\n'
        filtered_schema += '\n'.join(node_properties_types)
        filtered_schema += '\nRelationship properties:\n'
        filtered_schema += '\n'.join(rel_properties_types)
        filtered_schema += '\nThe relationships:\n'
        filtered_schema += '\n'.join(paths_nodes_rels_properties_types)

    else:
        #format the schema with neo4j library without inline props in paths
        filtered_schema = format_schema(structured_schema, is_enhanced=False)

    return filtered_schema
