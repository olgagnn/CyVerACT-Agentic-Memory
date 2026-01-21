from tqdm.auto import tqdm
from CyVer import SyntaxValidator, SchemaValidator, PropertiesValidator
from utils.Evaluation.output_metrics import *
from utils.Evaluation.cypher_metrics import *
import pandas as pd
from neo4j import GraphDatabase,basic_auth
import os 

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
    This functions computes the highest number of Cypher Metrics based on the 5 alternative ground-truth queries.
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


def calculate_scores(model_name, dataset, input_df, save=True):
    """
    The calculate_scores functions calculates the cypher metrics, output metrics and validator values for the generated queries
    of the provided dataframe and KG schema.
    """
    subfolder = dataset
    output_dir = f"{subfolder}/{model_name}/"
    # Create the directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    results_path_pkl = os.path.join(output_dir, f"{model_name}.pkl")
    results_path_xlsx = os.path.join(output_dir, f"{model_name}.xlsx")
    # Check if results file already exists
    if os.path.exists(results_path_pkl):
        df = pd.read_pickle(results_path_pkl)
    else:
        df = input_df.copy()
        #update df only with rows with  cypher queries (*in some results offshoreleaks is not evaluated)
        # df = df[df['generated_cypher'].notna()].reset_index(drop=True)

    # list of required columns
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
        if pd.notna(row['generated_cypher']) and str(row['generated_cypher']).strip() != '':
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

                ## CyVer validation for generated query
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

                # Check if it is syntax correct
                if syntax_correct:
                    pass_1_output_result = pass_1_output(driver, original_query, generated_query, database_name)
                    print(f"Pass@1 Output: {pass_1_output_result}")
                    df.at[i, 'Pass@1 Output'] = pass_1_output_result
                    jaccard_similarity_output_result = jaccard_similarity_output(driver, original_query, generated_query, database_name)
                    print(f"Jaccard Output: {jaccard_similarity_output_result}")
                    df.at[i, 'Jaccard Output'] = jaccard_similarity_output_result
                else:
                    df.at[i, 'Pass@1 Output'] = None
                    df.at[i, 'Jaccard Output'] = None

                if save :
                    # Save results
                    df.to_pickle(results_path_pkl)
                    df.to_excel(results_path_xlsx, index=False)# Set index=False to exclude the index column in Excel
            else:
                print(f"Skipping row {i}, already computed.")
    return df

def calculate_scores_benchmark(model_name, dataset, input_df):
    """
    The calculate_scores functions calculates the cypher metrics, output metrics and validator values for the generated queries
    of the provided dataframe and KG schema.
    """
    subfolder = dataset
    output_dir = f"{subfolder}/{model_name}/"
    # Create the directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    results_path_pkl = os.path.join(output_dir, f"{model_name}.pkl")
    results_path_xlsx = os.path.join(output_dir, f"{model_name}.xlsx")
    # Check if results file already exists
    if os.path.exists(results_path_pkl):
        df = pd.read_pickle(results_path_pkl)
    else:
        df = input_df.copy()
        #update df only with rows with  cypher queries (*in some results offshoreleaks is not evaluated)
        df = df[df['generated_cypher'].notna()].reset_index(drop=True)

        # initialize columns
        # df['Original Syntax Valid'] = None
        # df['Original Syntax Metadata'] = None
        # df['Original Schema Valid'] = None
        # df['Original Schema Metadata'] = None
        # df['Original Properties Valid'] = None
        # df['Original Properties Metadata'] = None
        df['Syntax Valid'] = None
        df['Syntax Metadata'] = None
        df['Schema Valid'] = None
        df['Schema Metadata'] = None
        df['Properties Valid'] = None
        df['Properties Metadata'] = None
        df['Pass@1 Output'] = None
        df['Jaccard Output'] = None
        df['BLEU'] = None
        df['Rouge-L Precision'] = None
        df['Rouge-L Recall'] = None
        df['Rouge-L F1-score'] = None
        df['Jaro Similarity'] = None
        df['Jaccard Similarity'] = None

    for i, row in tqdm(df.iterrows(), total=df.shape[0]):
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
         
            # if i == 133:
            # #             bluesky
            # # Original Query: MATCH (u1:User)-[:INTERACTED]->(u2:User) WHERE u2.area <> 1.77 RETURN DISTINCT u1.label
            # # Generated Query: MATCH (u:User)-[:INTERACTED]->(v:User) WHERE v.area <> 1.77 RETURN u.label
            #     print("Skipping row 133, bluesky dataset")
            #     continue
            # if i == 340: 
            #     # recommendations
            #     # Original Query: MATCH (u1:User)-[r1:RATED]->(m:Movie)<-[r2:RATED]-(u2:User) WHERE u1 <> u2 AND r1.rating <> r2.rating RETURN u1, u2, m
            #     # Generated Query: MATCH (u:User)-[:RATED]->(m:Movie)<-[:RATED]-(v:User) WHERE u.userId <> v.userId RETURN u.name, v.name
            #     print("Skipping row 340, recommendations dataset")
            #     continue
            # if i ==480 :
            #     print("Skipping row 480, recommendations dataset")
            #     continue
             
            # if i ==815  or i == 874 or i == 1256 or i == 1587 or i ==1608   :
            #     print("Skipping row 480, neoflix dataset")
            #     continue


           
            #Connect to the database
            driver = GraphDatabase.driver(database_url, auth=basic_auth(database_user, database_password) )
            
            syntax_validator = SyntaxValidator(driver)
            schema_validator = SchemaValidator(driver)
            properties_validator = PropertiesValidator(driver)
            
            generated_query = row['generated_cypher']
            generated_query = generated_query.replace("45", "4")
            
            if 'Cypher query ( Single Match, integrated properties)' in input_df:
                #its the sustain dataset
                original_query = row['Cypher query ( Single Match, integrated properties)']
            else:
                original_query = row['cypher']
                original_query = postprocess_output_cypher_by_neo4j(original_query) #apply their prostprocess function to make sure the original queries are valid

            print(i, database_name)
            print(f"Original Query: {original_query}")
            print(f"Generated Query: {generated_query}")
            
            # ## CyVer validation for original query
            # og_syntax_correct, og_syntax_metadata = syntax_validator.validate(original_query, database_name=database_name)
            # og_schema_valid, og_schema_metadata = schema_validator.validate(original_query, database_name=database_name)
            # og_properties_valid, og_properties_metadata = properties_validator.validate(original_query,database_name=database_name, strict=False)
            
            # print(f"Original Syntax Valid: {og_syntax_correct}")
            # print(f"Original Schema Valid: {og_schema_valid}")
            # print(f"Original Properties Valid: {og_properties_valid}")

            # df.at[i, 'Original Syntax Valid'] = og_syntax_correct        
            # df.at[i, 'Original Syntax Metadata'] = str(og_syntax_metadata)
            # df.at[i, 'Original Schema Valid'] = og_schema_valid
            # df.at[i, 'Original Schema Metadata'] = str(og_schema_metadata)
            # df.at[i, 'Original Properties Valid'] = og_properties_valid
            # df.at[i, 'Original Properties Metadata'] = str(og_properties_metadata)

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
            # Check if it is syntax correct
            if syntax_correct:
                try: 
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
    return df
