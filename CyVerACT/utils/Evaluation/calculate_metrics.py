from tqdm.auto import tqdm
from CyVer import SyntaxValidator, SchemaValidator, PropertiesValidator
from utils.Evaluation.output_metrics import *
from utils.Evaluation.cypher_metrics import *
import pandas as pd
from neo4j import GraphDatabase,basic_auth
import os 

"""
Evaluation entry points for benchmark scoring.

This module provides two benchmark functions:

1. `calculate_scores_benchmark_without_original_validation`
   Use this for the main benchmark evaluation when the reference/original
   queries are assumed to be valid (already validated) and only the generated queries need to be
   evaluated.

2. `calculate_scores_benchmark_with_original_validation`
   Use this when you also want to verify the KG validity of the
   reference/original queries, for example when auditing dataset quality or
   checking whether invalid references may affect the benchmark results.

Both functions:
- compute CyVer validation results for generated queries,
- compute text-based similarity metrics,
- compute execution-based output metrics when the generated query passes the
  required validity checks,
- keep rows with missing generated queries and assign `None` to the computed
  result columns for those rows.
"""


def postprocess_output_cypher_by_neo4j(output_cypher: str) -> str:
    # Remove any explanation. E.g.  MATCH...\n\n**Explanation:**\n\n -> MATCH...
    # Remove cypher indicator. E.g.```cypher\nMATCH...```` --> MATCH...
    # Note: Possible to have both:
    #   E.g. ```cypher\nMATCH...````\n\n**Explanation:**\n\n --> MATCH...
    
    # Handle escaped newline characters (\\n -> real \n)
    output_cypher = output_cypher.encode().decode('unicode_escape') # decode unicode escape sequences

    partition_by = "**Explanation:**"
    output_cypher, _, _ = output_cypher.partition(partition_by)
    output_cypher = output_cypher.strip("`\n")
    output_cypher = output_cypher.lstrip("cypher\n")
    output_cypher = output_cypher.strip("`\n ")
    output_cypher = output_cypher.replace('\n', ' ') ## added to fix benchmark dataset

    return output_cypher

### Calculate metrics
def compute_max(row):
    """
    Compute the maximum Cypher similarity scores across the available
    alternative ground-truth queries for a row.    
    """
    max_bleu_score = float('-inf')  # Start with the smallest possible number
    max_jaccard_score = float('-inf') 
    max_jaro_score = float('-inf')

    max_f1_score = float('-inf')
    best_recall = None
    best_precision = None

    columns_to_check = [
    'Cypher query ( Single Match, integrated properties)',
    'Cypher query 2 (Single Match, Where)',
    'Cypher query 3 (Multiple Match, integrated properties)',
    'Cypher query 4 (Multiple Match,Where)',
    'Alternative query'
    ]

    for col in columns_to_check:
        if pd.notna(row[col]):
            bleu = bleu_score(row[col], row['generated_cypher'])
            precision, recall, f1_score = rougeL_score(row[col], row['generated_cypher'])
            jaccard = jaccard_similarity_cypher(row[col], row['generated_cypher'])
            jaro = jaro_winkler_cypher(row[col], row['generated_cypher'])

            max_bleu_score = max(max_bleu_score, bleu)
            max_jaccard_score = max(max_jaccard_score, jaccard)
            max_jaro_score = max(max_jaro_score, jaro)
            
            if f1_score > max_f1_score:
                max_f1_score = f1_score
                best_recall = recall
                best_precision = precision

   
    return max_bleu_score,max_jaccard_score,max_jaro_score,best_precision,best_recall,max_f1_score



def calculate_scores_benchmark_without_original_validation(model_name,model_name_pkl, dataset, input_df):
    """
    Compute validation results and similarity/output metrics for benchmark
    evaluation without validating the original query.

    Use this function as the default benchmark evaluation pipeline when the
    original queries are assumed to be correct and only the generated queries
    need to be assessed.


    For each row, this function:
    - keeps rows with missing generated queries in the dataframe and assigns `None`
      to all computed result columns for those rows;
    - validates the generated query using syntax, schema, and property checks;
    - computes `is_KG_Valid_correct` for the generated query;
    - computes text-based similarity metrics between the original and generated
      queries;
    - computes execution-based output metrics only when:
      - the generated query passes the KG-validity check, and
      - the row answer is not
        `"I couldn't find any relevant information in the database"`.

    If execution is attempted and fails, the function assigns:
    - `Pass@1 Output = False`
    - `Jaccard Output = 0.0`

    Results are saved after each processed row in both pickle and Excel format.

    Notes:
    -  This function keeps all rows and explicitly handles missing generated queries.
    
    """
    subfolder = dataset
    output_dir = f"{subfolder}/{model_name}/"
    # Create the directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    full_path = os.path.abspath(output_dir)
    print("Full path to the directory:", full_path)

    results_path_pkl = os.path.join(output_dir, f"{model_name_pkl}.pkl")
    results_path_xlsx = os.path.join(output_dir, f"{model_name_pkl}.xlsx")
    # Check if results file already exists
    if os.path.exists(results_path_pkl):
        print('Reading existing results from pickle file...')
        df = pd.read_pickle(results_path_pkl)
    else:
        print('Reading the file we give')
        df = input_df.copy()
        # update df only with rows with  cypher queries (*in some results offshoreleaks is not evaluated)

    # df = df[df['generated_cypher'].notna()].reset_index(drop=True)

    required_columns = [
        'Syntax Valid',
        'Syntax Metadata',
        'Schema Valid',
        'Schema Metadata',
        'Properties Valid',
        'Properties Metadata',
        'is_KG_Valid_correct',
        'Pass@1 Output',
        'Jaccard Output',
        'BLEU',
        'Rouge-L Precision',
        'Rouge-L Recall',
        'Rouge-L F1-score',
        'Jaro Similarity',
        'Jaccard Similarity'
    ]

    # add columns that don't already exist
    for col in required_columns:
        if col not in df.columns:
            df[col] = None

    for i, row in tqdm(df.iterrows(), total=df.shape[0]):
        if pd.notna(row['generated_cypher']):
            if pd.isna(row['Syntax Valid']):
                # Get credentials
                required_cols = {'database_name', 'url', 'username', 'password'}
                if required_cols.issubset(df.columns):
                    database_url = row['url']
                    database_name = row['database_name']
                    database_user = row['username']
                    database_password = row['password']
                else:
                    #its the sustain dataset
                    database_url = os.getenv('database_url')
                    database_name = os.getenv('database_name')
                    database_user = os.getenv('database_user')
                    database_password = os.getenv('database_password')
                    
                #Connect to the database
                driver = GraphDatabase.driver(database_url, auth=basic_auth(database_user, database_password) )
                
                syntax_validator = SyntaxValidator(driver)
                schema_validator = SchemaValidator(driver)
                properties_validator = PropertiesValidator(driver)
                
                generated_query = row['generated_cypher']
                # generated_query = generated_query.replace("45", "4")
                
                if 'Cypher query ( Single Match, integrated properties)' in input_df:
                    #its the sustain dataset
                    original_query = row['Cypher query ( Single Match, integrated properties)']
                else:
                    original_query = row['cypher']
                    original_query = postprocess_output_cypher_by_neo4j(original_query) #apply their prostprocess function to make sure the original queries are valid

                print(i, database_name)
                print(f"Original Query: {original_query}")
                print(f"Generated Query: {generated_query}")

                # CyVer validation for generated query
                syntax_correct, syntax_metadata = syntax_validator.validate(generated_query, database_name=database_name)
                schema_valid, schema_metadata = schema_validator.validate(generated_query, database_name=database_name)
                properties_valid, properties_metadata = properties_validator.validate(generated_query,database_name=database_name, strict=False)
                
                print(f"Syntax Valid: {syntax_correct}")
                print(f"Schema Valid: {schema_valid}")
                print(f"Properties Valid: {properties_valid}")

                df.at[i, 'Syntax Valid'] = syntax_correct        
                df.at[i, 'Syntax Metadata'] = str(syntax_metadata)
                df.at[i, 'Schema Valid'] = schema_valid
                df.at[i, 'Schema Metadata'] = str(schema_metadata)
                df.at[i, 'Properties Valid'] = properties_valid
                df.at[i, 'Properties Metadata'] = str(properties_metadata)

                kg_valid_check = (
                                (df.at[i,'Schema Valid'] == 1)
                                & ((df.at[i,'Properties Valid'] == 1) | pd.isna(df.at[i,'Properties Valid']))
                                & (df.at[i,'Syntax Valid'] == True)
                            )
                print('Is KG Valid:',kg_valid_check)
                df.at[i,'is_KG_Valid_correct'] = kg_valid_check
                df.at[i,'is_KG_Valid_correct'] = df.at[i,'is_KG_Valid_correct']
                
                #metrics
                if 'Cypher query ( Single Match, integrated properties)' in input_df:
                    #its the sustain dataset, so i have several versions of original cypher queries
                    bleu,jaccard,jaro,rouge_precision,rouge_recall,rouge_f1_score = compute_max(row)
                else:
                    bleu = bleu_score(original_query, row['generated_cypher'])
                    rouge_precision, rouge_recall, rouge_f1_score = rougeL_score(original_query, row['generated_cypher'])
                    jaccard = jaccard_similarity_cypher(original_query, row['generated_cypher'])
                    jaro = jaro_winkler_cypher(original_query, row['generated_cypher'])

                print(f"BLEU: {bleu}")
                print(f"Rouge-L Precision: {rouge_precision}")
                print(f"Rouge-L Recall: {rouge_recall}")
                print(f"Rouge-L F1-score: {rouge_f1_score}")
                print(f"Jaro Similarity: {jaro}")
                print(f"Jaccard Similarity: {jaccard}")

                df.at[i, 'BLEU'] = bleu
                df.at[i, 'Rouge-L Precision'] = rouge_precision
                df.at[i, 'Rouge-L Recall'] = rouge_recall
                df.at[i, 'Rouge-L F1-score'] = rouge_f1_score
                df.at[i, 'Jaro Similarity'] = jaro
                df.at[i, 'Jaccard Similarity'] = jaccard

                if (kg_valid_check == False) or (df.at[i, 'answer'] == "I couldn't find any relevant information in the database"):
                    df.at[i, 'Pass@1 Output'] = None
                    df.at[i, 'Jaccard Output'] = None
                    print('KG valid check', kg_valid_check)
                    print('answer check', df.at[i, 'answer'])
                else:
                    # Check if it is syntax correct
                    if syntax_correct:
                        try: 
                            print('Calculating pass and jaccard output metrics...')
                            original_output = execute_query(driver, original_query, database_name)
                            generated_output = execute_query(driver, generated_query, database_name)

                            # If the output are whole nodes or relationships, extract the properties to compare the similarity
                            original_properties = [extract_properties(record) for record in original_output]
                            generated_properties = [extract_properties(record) for record in generated_output]

                            jaccard_similarity_output_result = similarity(original_properties, generated_properties, "order by" in f"{original_query}".lower())

                            if jaccard_similarity_output_result == 1: 
                                pass_1_output_result =True
                            else: 
                                pass_1_output_result = False
                            
                        except Exception as e:
                            pass_1_output_result = False
                            jaccard_similarity_output_result = 0.0 # return minimum similarity.
                        
                        # pass_1_output_result = pass_1_output(driver, original_query, generated_query, database_name)
                        print(f"Pass@1 Output: {pass_1_output_result}")
                        df.at[i, 'Pass@1 Output'] = pass_1_output_result
                        # jaccard_similarity_output_result = jaccard_similarity_output(driver, original_query, generated_query, database_name)
                        print(f"Jaccard Output: {jaccard_similarity_output_result}")
                        df.at[i, 'Jaccard Output'] = jaccard_similarity_output_result
                    else:
                            df.at[i, 'Pass@1 Output'] = None
                            df.at[i, 'Jaccard Output'] = None

                # Save results
                df.to_pickle(results_path_pkl)
                df.to_excel(results_path_xlsx, index=False)# Set index=False to exclude the index column in Excel
            else:
                print(f"Skipping row {i}, already computed.")
        else:
            print(f"row {i}")
            print('None query generated')
            for col in required_columns:
                df.at[i, col] = None
    return df


def calculate_scores_benchmark_with_original_validation(model_name,model_name_pkl, dataset, input_df):
    """
    Compute validation results and similarity/output metrics for benchmark
    evaluation while validating  both the original and generated queries.

    Use this function when you want the same benchmark evaluation as
    `calculate_scores_benchmark_without_original_validation`, but also need to
    assess whether the original/reference queries are KG-valid.

    For each row, this function:
    - keeps rows with missing generated queries in the dataframe and assigns `None`
      to all computed result columns for those rows;
    - validates both the original query and the generated query using syntax,
      schema, and property checks;
    - computes `is_KG_Valid_correct` for the generated query;
    - computes text-based similarity metrics between the original and generated
      queries;
    - computes execution-based output metrics only when:
      - the generated query passes the KG-validity check, and
      - the row answer is not
        `"I couldn't find any relevant information in the database"`.

    If execution is attempted and fails, the function assigns:
    - `Pass@1 Output = False`
    - `Jaccard Output = 0.0`

    Results are saved after each processed row in both pickle and Excel format.

    Notes:
    -  This function keeps all rows and explicitly handles missing generated queries.
    
    """
    subfolder = dataset
    output_dir = f"{subfolder}/{model_name}/"
    # Create the directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    full_path = os.path.abspath(output_dir)
    print("Full path to the directory:", full_path)

    results_path_pkl = os.path.join(output_dir, f"{model_name_pkl}.pkl")
    results_path_xlsx = os.path.join(output_dir, f"{model_name_pkl}.xlsx")
    # Check if results file already exists
    if os.path.exists(results_path_pkl):
        print('Reading existing results from pickle file...')
        df = pd.read_pickle(results_path_pkl)
    else:
        print('Reading the file we give')
        df = input_df.copy()
        # update df only with rows with  cypher queries (*in some results offshoreleaks is not evaluated)

    # df = df[df['generated_cypher'].notna()].reset_index(drop=True)

    required_columns = [
        'Original Syntax Valid',
        'Original Syntax Metadata',
        'Original Schema Valid',
        'Original Schema Metadata',
        'Original Properties Valid',
        'Original Properties Metadata',
        'Syntax Valid',
        'Syntax Metadata',
        'Schema Valid',
        'Schema Metadata',
        'Properties Valid',
        'Properties Metadata',
        'is_KG_Valid_correct',
        'Pass@1 Output',
        'Jaccard Output',
        'BLEU',
        'Rouge-L Precision',
        'Rouge-L Recall',
        'Rouge-L F1-score',
        'Jaro Similarity',
        'Jaccard Similarity'
    ]

    # add columns that don't already exist
    for col in required_columns:
        if col not in df.columns:
            df[col] = None

    for i, row in tqdm(df.iterrows(), total=df.shape[0]):
        if pd.notna(row['generated_cypher']):
            if pd.isna(row['Syntax Valid']):
                # Get credentials
                required_cols = {'database_name', 'url', 'username', 'password'}
                if required_cols.issubset(df.columns):
                    database_url = row['url']
                    database_name = row['database_name']
                    database_user = row['username']
                    database_password = row['password']
                else:
                    #its the sustain dataset
                    database_url = os.getenv('database_url')
                    database_name = os.getenv('database_name')
                    database_user = os.getenv('database_user')
                    database_password = os.getenv('database_password')
                    
                #Connect to the database
                driver = GraphDatabase.driver(database_url, auth=basic_auth(database_user, database_password) )
                
                syntax_validator = SyntaxValidator(driver)
                schema_validator = SchemaValidator(driver)
                properties_validator = PropertiesValidator(driver)
                
                generated_query = row['generated_cypher']
                # generated_query = generated_query.replace("45", "4")
                
                if 'Cypher query ( Single Match, integrated properties)' in input_df:
                    #its the sustain dataset
                    original_query = row['Cypher query ( Single Match, integrated properties)']
                else:
                    original_query = row['cypher']
                    original_query = postprocess_output_cypher_by_neo4j(original_query) #apply their prostprocess function to make sure the original queries are valid

                print(i, database_name)
                print(f"Original Query: {original_query}")
                print(f"Generated Query: {generated_query}")

                   ## CyVer validation for original query
                og_syntax_correct, og_syntax_metadata = syntax_validator.validate(original_query, database_name=database_name)
                og_schema_valid, og_schema_metadata = schema_validator.validate(original_query, database_name=database_name)
                og_properties_valid, og_properties_metadata = properties_validator.validate(original_query,database_name=database_name, strict=False)
                
                print(f"Original Syntax Valid: {og_syntax_correct}")
                print(f"Original Schema Valid: {og_schema_valid}")
                print(f"Original Properties Valid: {og_properties_valid}")

                df.at[i, 'Original Syntax Valid'] = og_syntax_correct        
                df.at[i, 'Original Syntax Metadata'] = str(og_syntax_metadata)
                df.at[i, 'Original Schema Valid'] = og_schema_valid
                df.at[i, 'Original Schema Metadata'] = str(og_schema_metadata)
                df.at[i, 'Original Properties Valid'] = og_properties_valid
                df.at[i, 'Original Properties Metadata'] = str(og_properties_metadata)

                # CyVer validation for generated query
                syntax_correct, syntax_metadata = syntax_validator.validate(generated_query, database_name=database_name)
                schema_valid, schema_metadata = schema_validator.validate(generated_query, database_name=database_name)
                properties_valid, properties_metadata = properties_validator.validate(generated_query,database_name=database_name, strict=False)
                
                print(f"Syntax Valid: {syntax_correct}")
                print(f"Schema Valid: {schema_valid}")
                print(f"Properties Valid: {properties_valid}")

                df.at[i, 'Syntax Valid'] = syntax_correct        
                df.at[i, 'Syntax Metadata'] = str(syntax_metadata)
                df.at[i, 'Schema Valid'] = schema_valid
                df.at[i, 'Schema Metadata'] = str(schema_metadata)
                df.at[i, 'Properties Valid'] = properties_valid
                df.at[i, 'Properties Metadata'] = str(properties_metadata)

                kg_valid_check = (
                                (df.at[i,'Schema Valid'] == 1)
                                & ((df.at[i,'Properties Valid'] == 1) | pd.isna(df.at[i,'Properties Valid']))
                                & (df.at[i,'Syntax Valid'] == True)
                            )
                print('Is KG Valid:',kg_valid_check)
                df.at[i,'is_KG_Valid_correct'] = kg_valid_check
                df.at[i,'is_KG_Valid_correct'] = df.at[i,'is_KG_Valid_correct']
                
                #metrics
                if 'Cypher query ( Single Match, integrated properties)' in input_df:
                    #its the sustain dataset, so i have several versions of original cypher queries
                    bleu,jaccard,jaro,rouge_precision,rouge_recall,rouge_f1_score = compute_max(row)
                else:
                    bleu = bleu_score(original_query, row['generated_cypher'])
                    rouge_precision, rouge_recall, rouge_f1_score = rougeL_score(original_query, row['generated_cypher'])
                    jaccard = jaccard_similarity_cypher(original_query, row['generated_cypher'])
                    jaro = jaro_winkler_cypher(original_query, row['generated_cypher'])

                print(f"BLEU: {bleu}")
                print(f"Rouge-L Precision: {rouge_precision}")
                print(f"Rouge-L Recall: {rouge_recall}")
                print(f"Rouge-L F1-score: {rouge_f1_score}")
                print(f"Jaro Similarity: {jaro}")
                print(f"Jaccard Similarity: {jaccard}")

                df.at[i, 'BLEU'] = bleu
                df.at[i, 'Rouge-L Precision'] = rouge_precision
                df.at[i, 'Rouge-L Recall'] = rouge_recall
                df.at[i, 'Rouge-L F1-score'] = rouge_f1_score
                df.at[i, 'Jaro Similarity'] = jaro
                df.at[i, 'Jaccard Similarity'] = jaccard

                if (kg_valid_check == False) or (df.at[i, 'answer'] == "I couldn't find any relevant information in the database"):
                    df.at[i, 'Pass@1 Output'] = None
                    df.at[i, 'Jaccard Output'] = None
                    print('KG valid check', kg_valid_check)
                    print('answer check', df.at[i, 'answer'])
                else:
                    # Check if it is syntax correct
                    if syntax_correct:
                        try: 
                            print('Calculating pass and jaccard output metrics...')
                            original_output = execute_query(driver, original_query, database_name)
                            generated_output = execute_query(driver, generated_query, database_name)

                            # If the output are whole nodes or relationships, extract the properties to compare the similarity
                            original_properties = [extract_properties(record) for record in original_output]
                            generated_properties = [extract_properties(record) for record in generated_output]

                            jaccard_similarity_output_result = similarity(original_properties, generated_properties, "order by" in f"{original_query}".lower())

                            if jaccard_similarity_output_result == 1: 
                                pass_1_output_result =True
                            else: 
                                pass_1_output_result = False
                            
                        except Exception as e:
                            pass_1_output_result = False
                            jaccard_similarity_output_result = 0.0 # return minimum similarity.
                        
                        # pass_1_output_result = pass_1_output(driver, original_query, generated_query, database_name)
                        print(f"Pass@1 Output: {pass_1_output_result}")
                        df.at[i, 'Pass@1 Output'] = pass_1_output_result
                        # jaccard_similarity_output_result = jaccard_similarity_output(driver, original_query, generated_query, database_name)
                        print(f"Jaccard Output: {jaccard_similarity_output_result}")
                        df.at[i, 'Jaccard Output'] = jaccard_similarity_output_result
                    else:
                            df.at[i, 'Pass@1 Output'] = None
                            df.at[i, 'Jaccard Output'] = None

                # Save results
                df.to_pickle(results_path_pkl)
                df.to_excel(results_path_xlsx, index=False)# Set index=False to exclude the index column in Excel
            else:
                print(f"Skipping row {i}, already computed.")
        else:
            print(f"row {i}")
            print('None query generated')
            for col in required_columns:
                df.at[i, col] = None
    return df
