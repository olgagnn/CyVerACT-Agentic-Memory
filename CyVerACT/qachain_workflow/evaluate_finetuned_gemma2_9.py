from graph import app 
import pandas as pd
import os
from tqdm.auto import tqdm
import torch
from Configuration.models import models #import models to evaluate

def evaluate_model (model_name, model, dataset):
    ''' 
    Evaluate the selected model on the given dataset, by invoking the graph workflow.
    Save the dataframe with the questions and the generated cypher queries to the Results folder.
    Return the dataframe
    '''
    torch.cuda.empty_cache()#clear gpu cache
    # Get datasets 
    if dataset =='sustain':
        df = pd.read_excel('../data/text2cypher-sustaingraph/sustaintest.xlsx',sheet_name='Queries')
        subfolder = 'SustainDataset'
    elif dataset == 'benchmark2025':
        df = pd.read_excel('../data/text2cypher-2025v1/test.xlsx')
        #update df only with rows with a database access
        df = df[df['url'].notna()].reset_index(drop=True)
        subfolder = 'BenchmarkDataset2025'
    elif dataset == 'benchmark2024':
        df = pd.read_excel('../data/text2cypher-2024v1/test.xlsx')
        #update df only with rows with a database access
        df = df[df['url'].notna()].reset_index(drop=True)
        subfolder = 'BenchmarkDataset2024'
    
    output_dir = f"Results/{subfolder}/{model_name}/"
    # Create the directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    results_path_pkl = os.path.join(output_dir, f"{model_name}.pkl")
    results_path_xlsx = os.path.join(output_dir, f"{model_name}.xlsx")

    # Check if results file already exists
    if os.path.exists(results_path_xlsx):
        df_results = pd.read_excel(results_path_xlsx)
    else:# Run model on dataset
        df_results = df.copy() # Copy of the df with questions and expected answers, to add the answers of the llm 
        # Now define additional columns in df_results to store LLM results:
        df_results['generated_cypher'] = None 
        df_results['answer'] = None
        df_results['path'] = None           # Use None so we can store a list
        df_results['output'] = None           # Use None so we can store a list
        df_results['cypher_errors_history'] = None           # Use None so we can store a list
        df_results['cypher_errors'] = None           # Use None so we can store a list
        df_results['is_KG_Valid_correct'] = None           # Use None so we can store a list

    config = {'configurable': {'model': model, 'model_name':model_name, 'attempts_w_filtered':5, 'total_attempts':10},'recursion_limit':50}
    
    print(f'Starting evaluation for {model_name} on {dataset} ...')
    # results=[]
    # Iterate over each row and compute only if not already done
    for i, row in tqdm(df_results.iterrows(), total=df_results.shape[0]):
    # i=1
    # row = df_results.loc[i]
        if pd.isna(row['generated_cypher']):
            question = row['Question'] if dataset == 'sustain' else row['question']
            print(i,question)
            # print(row['cypher'])
            
            # Get credentials
            required_cols = {'database_name', 'url', 'username', 'password'}
            if required_cols.issubset(df_results.columns):
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
            if database_name == 'offshoreleaks':
                print(f'Skipping row {i}, to avoid memory error in {database_name}')
                continue
            if i==1484:
                print(f"Skipping row {i} due to memory issues")
                continue
            else:# Configuration 
                inputs = {
                    'question':question,
                    'database_url': database_url,
                    'database_name':database_name,
                    'database_user':database_user,
                    'database_password':database_password
                }
                torch.cuda.empty_cache() #clear gpu cache
            
                # Run the graph and save outputs
                result =app.invoke(inputs, config =config) #,debug=False
                df_results.at[i, 'generated_cypher'] = result['cypher_statement']
                df_results.at[i, 'output'] = str(result['database_records'])
                # df_results.at[i, 'path'] = result['path']
                # df_results.at[i, 'cypher_errors'] = result['cypher_errors']
                # df_results.at[i, 'cypher_errors_history'] = result['cypher_errors_history']
                # df_results.at[i, 'is_KG_Valid_correct'] = result['is_KG_Valid_correct']
                # df_results.at[i, 'answer'] = result['answer']
                # if ('schema_retriever' in result['path']) and result['is_KG_Valid_correct']:
                #     df_results.at[i, 'is_KG_Valid_correct_with_full_schema'] = True
                # else:
                #     df_results.at[i, 'is_KG_Valid_correct_with_full_schema'] = False
                # results.append(result)
                # torch.cuda.empty_cache()#clear gpu cache
                
                # Save results
                df_results.to_pickle(results_path_pkl)
                df_results.to_excel(results_path_xlsx, index=False)# Set index=False to exclude the index column in Excel
        else:
            print(f"Skipping row {i}, already computed.")
            
    return df_results



model_name = 'finetuned_gemma2_9b_local'
df_results = evaluate_model (model_name, models[model_name](), 'benchmark2025')