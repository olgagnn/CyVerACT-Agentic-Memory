'''
Download the dataset from hugging face, fix typos and add information access
(url, username ,password) for the databases.
Save the datasets in the data folder.
'''
import pandas as pd

# Get datasets from huggingface
huggingface_repos = ["hf://datasets/neo4j/text2cypher-2024v1/", 
                     "hf://datasets/neo4j/text2cypher-2025v1/"]
splits = {
    "hf://datasets/neo4j/text2cypher-2024v1/":{ 'train': 'data/train-00000-of-00001.parquet', 
                                                'test': 'data/test-00000-of-00001.parquet'},
    "hf://datasets/neo4j/text2cypher-2025v1/":{ 'train': 'data/train.parquet', 
                                                 'test': 'data/test.parquet'}
}
for huggingface_repo in huggingface_repos:
    print(f"Downloading {huggingface_repo}...")
    # Download the datasets from huggingface
    df_train = pd.read_parquet(huggingface_repo + splits[huggingface_repo]['train'])
    df_test = pd.read_parquet(huggingface_repo + splits[huggingface_repo]['test'])


    #Note: In the database_reference_alias column, 
    # there is a typo for 'neo4jlabs_demo_db_eoflix', 
    # it should be 'neo4jlabs_demo_db_neoflix'.

    df_train['database_reference_alias'] = df_train['database_reference_alias'].replace('neo4jlabs_demo_db_eoflix', 'neo4jlabs_demo_db_neoflix')
    df_test['database_reference_alias'] = df_test['database_reference_alias'].replace('neo4jlabs_demo_db_eoflix', 'neo4jlabs_demo_db_neoflix')


    # For the databases hosted in neo4j labs,  we extract database name from the 'database_reference_alias' column
    #  and access information from https://github.com/neo4j-graph-examples/demo.neo4jlabs.com?tab=readme-ov-file 
    # (username and password are the same as the database name for read-only user)
    # The server URL is: https://demo.neo4jlabs.com:7473

    def add_credentials(df):
        df['url'] = df['database_reference_alias'].apply(lambda x:"neo4j+s://demo.neo4jlabs.com" if isinstance(x, str) else None) 
        df['database_name'] = df['database_reference_alias'].apply(lambda x: x.split("_")[-1] if isinstance(x, str) else None)
        df['username'] = df['database_reference_alias'].apply(lambda x: x.split("_")[-1] if isinstance(x, str) else None)
        df['password'] = df['database_reference_alias'].apply(lambda x: x.split("_")[-1] if isinstance(x, str) else None)
        return df   


    df_test = add_credentials(df_test)
    df_train = add_credentials(df_train)

    #Save modified datasets to data folder
    subfolder = huggingface_repo.split("/")[-2]
    df_train.to_excel(f"data/{subfolder}/train.xlsx", index=False, engine="openpyxl")
    print(f'Saving train dataset at data/{subfolder}/train.xlsx')
    df_test.to_excel(f"data/{subfolder}/test.xlsx", index=False, engine="openpyxl")
    print(f'Saving test dataset at data/{subfolder}/test.xlsx')