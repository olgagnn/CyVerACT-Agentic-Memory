import argparse
import os
import pandas as pd
from neo4j import GraphDatabase, basic_auth
import sys
sys.path.append('../../')
from utils.Evaluation.output_metrics import *

def postprocess_output_cypher_by_neo4j(output_cypher: str) -> str:
    output_cypher = output_cypher.encode().decode('unicode_escape')
    output_cypher, _, _ = output_cypher.partition("**Explanation:**")
    output_cypher = output_cypher.strip("`\n").lstrip("cypher\n").strip("`\n ")
    output_cypher = output_cypher.replace('\n', ' ')
    return output_cypher

def main(i):
    model_name = 'finetuned_gemma2_9b_local'
    path = f'./BenchmarkDataset2025/{model_name}/{model_name}.pkl'
    df = pd.read_pickle(path)

    # Load row
    row = df.iloc[i]
    database_url = row['url']
    database_name = row['database_name']
    database_user = row['username']
    database_password = row['password']

    # Connect to database
    driver = GraphDatabase.driver(database_url, auth=basic_auth(database_user, database_password))

    # Prepare queries
    original_query = postprocess_output_cypher_by_neo4j(row['cypher'])
    generated_query = row['generated_cypher']

    # Evaluate
     
    try: 
        print('Start evaluation')
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
        print('Finished evaluation')
    except Exception as e:
        print(f"Error during evaluation: {e}")
        pass_1_output_result = False
        jaccard_similarity_output_result = 0.0 # return minimum similarity.

    # pass_1_output_result = pass_1_output(driver, original_query, generated_query, database_name)
    print(f"Pass@1 Output: {pass_1_output_result}")
    df.at[i, 'Pass@1 Output'] = pass_1_output_result

    # jaccard_similarity_output_result = jaccard_similarity_output(driver, original_query, generated_query, database_name)
    print(f"Jaccard Output: {jaccard_similarity_output_result}")
    df.at[i, 'Jaccard Output'] = jaccard_similarity_output_result

    # print("Original Query:\n", original_query)

    # Save updated results
    output_dir = f'BenchmarkDataset2025/{model_name}/'
    os.makedirs(output_dir, exist_ok=True)
    df.to_pickle(os.path.join(output_dir, f"{model_name}.pkl"))
    df.to_excel(os.path.join(output_dir, f"{model_name}.xlsx"), index=False)
    print(f"Results saved to {output_dir}")
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run evaluation on a specific row of the benchmark dataset.")
    parser.add_argument("i", type=int, help="Row index to evaluate")
    args = parser.parse_args()
    main(args.i)