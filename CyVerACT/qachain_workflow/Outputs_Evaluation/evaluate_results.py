import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import math
import ast
import sys
sys.path.append('../../')
from utils.Evaluation.calculate_metrics import calculate_scores_benchmark


def extract_error_types(nested_list):
    return [s.split(',')[0] for sublist in nested_list for s in sublist]

def calculate_metrics(model_name, dataset, path):
    df = pd.read_excel(path)

    df.rename(columns={'generated_cypher': 'Generated_Cypher'}, inplace=True)

    #Calcultes the metrics and saved the the df with the results and the evaluation metrics
    df = calculate_scores_benchmark(model_name, dataset, df)

    # df['error_codes'] = df['cypher_errors_history'].apply(extract_error_types)
    df['error_codes'] =df['cypher_errors_history'].apply(ast.literal_eval).apply(extract_error_types)

    return df

def extract_dfs(df):

    kg_valid_queries_df = df[df['is_KG_Valid_correct']==True].reset_index(drop=True)
    unavailable_output_df = df[df['answer']=="I couldn't find any relevant information in the database"].reset_index(drop=True)
    kg_valid_queries_with_full_schema_df = df[df['is_KG_Valid_correct_with_full_schema']==True].reset_index(drop=True)
    kg_valid_queries_with_filtered_schema_df = df[(df['is_KG_Valid_correct_with_full_schema']==False) & (df['is_KG_Valid_correct']==True)].reset_index(drop=True)

    return kg_valid_queries_df,unavailable_output_df,kg_valid_queries_with_full_schema_df,kg_valid_queries_with_filtered_schema_df


# SustainDataset
dataset = 'BenchmarkDataset2025'
models =['finetuned_gemma2_9b_local']
for model_name in models:
    path = f'../Results/{dataset}/{model_name}/{model_name}.xlsx'
    df = calculate_metrics(model_name, dataset,path)