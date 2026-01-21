from langchain_openai import  ChatOpenAI
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint 
from langchain_huggingface.llms import HuggingFacePipeline
from huggingface_hub import InferenceClient
# from langchain_runpod import RunPod, ChatRunPod
from langchain_huggingface.llms import HuggingFacePipeline
from transformers import AutoTokenizer, pipeline
import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)
import os 
from dotenv import load_dotenv
# https://huggingface.co/neo4j/text2cypher-gemma-2-9b-it-finetuned-2024v1
# Load environment variables from .env file
load_dotenv()
# from transformers import pipeline

#----Openai chatmodel--------------

def get_gpt_4o():
    return  ChatOpenAI(
            model="gpt-4o", 
            temperature=0,
            api_key= os.getenv('OPENAI_API_KEY'),
        )
#--------Huggingface chatmodel--------------
#https://huggingface.co/blog/langchain?utm_source=chatgpt.com
#https://python.langchain.com/docs/integrations/providers/huggingface/


###########################################
########### Neo4jBenchmark ##################
###########################################


def get_llama3_1_8b():
    return ChatHuggingFace(llm=HuggingFaceEndpoint(
                                        # repo_id="meta-llama/Llama-3.1-8B-Instruct",
                                        endpoint_url = os.getenv('llama3_1_8b_hf_url'),
                                        task="text-generation",
                                        max_new_tokens=512,
                                        top_k=20,
                                        top_p=0.9,
                                        do_sample=True,
                                        temperature=0.01,
                                        # repetition_penalty=1.03,
                                    ))


#Tomaz finetuned llama3_1_8b
# https://huggingface.co/tomasonjo/text2cypher-demo-16bit
def get_finetuned_tomasonjo_llama3_1_8b():
    return ChatHuggingFace(llm=HuggingFaceEndpoint(
                                        # repo_id="tomasonjo/text2cypher-demo-16bit",
                                        endpoint_url = os.getenv('finetuned_tomasonjo_llama3_1_8b_hf_url'),
                                        task="text-generation",
                                        max_new_tokens=512,
                                        top_k=20,
                                        top_p=0.9,
                                        do_sample=True,
                                        temperature=0.01,
                                        # repetition_penalty=1.03,
                                    ))



def get_gemma2_9b():
    return ChatHuggingFace(llm=HuggingFaceEndpoint(
                                        # repo_id="google/gemma-2-9b-it",
                                        endpoint_url = os.getenv('gemma2_9b_hf_url'),
                                        task="text-generation",
                                        max_new_tokens=512,
                                        top_k=20,
                                        top_p=0.9,
                                        do_sample=True,
                                        temperature=0.01,
                                        # repetition_penalty=1.03,
                                    ))


def get_finetuned_gemma2_9b():
    return ChatHuggingFace(llm=HuggingFaceEndpoint(
                                        # repo_id="neo4j/text2cypher-gemma-2-9b-it-finetuned-2024v1",
                                        endpoint_url = os.getenv('finetuned_gemma2_9b_hf_url'),
                                        task="text-generation",
                                        max_new_tokens=512,
                                        top_k=20,
                                        top_p=0.9,
                                        do_sample=True,
                                        temperature=0.01,
                                        # repetition_penalty=1.03,
                                    ))

def get_finetuned_azzedde_llama3_1_8b():
    return ChatHuggingFace(llm=HuggingFaceEndpoint(
                                        # repo_id="Azzedde/llama3.1-8b-text2cypher",
                                        endpoint_url = os.getenv('finetuned_azzedde_llama3_1_8b_hf_url'),
                                        task="text-generation",
                                        max_new_tokens=512,
                                        top_k=20,
                                        top_p=0.9,
                                        do_sample=True,
                                        temperature=0.01,
                                        # repetition_penalty=1.03,
                                    ))



######################################
########SUSTAIN MODELS ###############
######################################

def get_llama3_2_3b():
    return ChatHuggingFace(llm=HuggingFaceEndpoint(
                                        # repo_id="meta-llama/Llama-3.2-3B-Instruct",
                                        #run from dedicated endpoints in huggingface
                                        endpoint_url= os.getenv('DEDICATED_HF_URL_LLAMA_3_2_3B'),
                                        task="text-generation",
                                        max_new_tokens=512,
                                        top_k=20,
                                        top_p=0.9,
                                        do_sample=True,
                                        temperature=0.01,
                                        # repetition_penalty=1.03,
                                    ))


def get_qwen2_5_7b():
    return ChatHuggingFace(llm=HuggingFaceEndpoint(
                                        # repo_id="Qwen/Qwen2.5-7B-Instruct",
                                        endpoint_url = os.getenv('qwen2_5_7b_hf_url'),
                                        task="text-generation",
                                        max_new_tokens=512,
                                        top_k=20,
                                        top_p=0.9,
                                        do_sample=True,
                                        temperature=0.01,
                                        # repetition_penalty=1.03,
                                    ))




def get_qwen2_5_Coder_32b():
    return ChatHuggingFace(llm=HuggingFaceEndpoint(
                                        # repo_id="Qwen/Qwen2.5-Coder-32B-Instruct",
                                        endpoint_url = os.getenv('DEDICATED_HF_URL_QWEN_CODER_32B'),
                                        task="text-generation",
                                        max_new_tokens=512,
                                        top_k=20,
                                        top_p=0.9,
                                        do_sample=True,
                                        temperature=0.01,
                                        # repetition_penalty=1.03,
                                    ))

def get_qwen2_5_72b():
    # return ChatHuggingFace(llm=HuggingFaceEndpoint(
    #                                     repo_id="Qwen/Qwen2.5-72B-Instruct",
    #                                     task="text-generation",
    #                                     max_new_tokens=512,
    #                                     top_k=20,
    #                                     top_p=0.9,
    #                                     do_sample=True,
    #                                     temperature=0.01,
    #                                     # repetition_penalty=1.03,
    #                                 ))
    return ChatOpenAI(
            model="qwen/qwen-2.5-72b-instruct:free",
            openai_api_key = os.getenv("OPENROUTER_API_KEY"),
            openai_api_base = 'https://openrouter.ai/api/v1',
            # default_headers = {
            #         "HTTP-Referer": "https://www.usemynt.com/",
            #         "X-Title": "Mynt"
            # },
            # top_k=20,
            top_p=0.9,
            temperature=0.01,
            streaming=True
        )


# Run locally in GPU    
def get_llama3_2_3b_local():  
    tokenizer = AutoTokenizer.from_pretrained("meta-llama/Llama-3.2-3B-Instruct")
    tokenizer.pad_token = tokenizer.eos_token
    return ChatHuggingFace(llm= HuggingFacePipeline(pipeline=pipeline("text-generation",
                                                        model="meta-llama/Llama-3.2-3B-Instruct",
                                                        # tokenizer=tokenizer,
                                                        max_new_tokens=512,
                                                        top_k=20,
                                                        top_p=0.9,
                                                        do_sample=True,
                                                        temperature=0.01,
                                                        # repetition_penalty=1.03,
                                                        torch_dtype=torch.bfloat16,
                                                        pad_token_id=tokenizer.pad_token_id
                                                    )))

# Run locally in GPU    
def get_finetuned_gemma2_9b_local():  
    model_name = "neo4j/text2cypher-gemma-2-9b-it-finetuned-2024v1"
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=bnb_config,
        torch_dtype=torch.bfloat16,
        attn_implementation="eager",
        low_cpu_mem_usage=True,
    )
    return ChatHuggingFace(llm= HuggingFacePipeline(pipeline=pipeline("text-generation",
                                                        model=model,
                                                        tokenizer=tokenizer,
                                                        max_new_tokens=512,
                                                        top_k=20,
                                                        top_p=0.9,
                                                        do_sample=True,
                                                        temperature=0.01,
                                                        # repetition_penalty=1.03,
                                                        torch_dtype=torch.bfloat16,
                                                        pad_token_id=tokenizer.eos_token_id
                                                        ),
                                                    ), 
                                                    model_id=model_name
                                                   )
def get_finetuned_gemma2_9b_runpod():
    return RunPod(endpoint_id=os.getenv('RUNPOD_ENDPOINT_ID_FINETUNED_GEMMA_2_9B'),  # Your RunPod serverless endpoint ID, oprional if set in env variables
                    model_kwargs={
                        "max_new_tokens": 512,
                        "top_k": 20,
                        "top_p":0.9,
                        "temperature": 0.01,
                        # Add other parameters supported by your endpoint handler
                    },
                    # Optional: Adjust polling
                    # poll_interval=0.3,
                    # max_polling_attempts=100
                )
# def get_finetuned_gemma2_9b_runpod():
#     print("Using RunPod for finetuned gemma2_9b")
#     return  ChatOpenAI(
#             base_url=f"https://api.runpod.ai/v2/q7syv12dex40u0/openai/v1",
#             temperature=0,
#             api_key= os.getenv('RUNPOD_API_KEY'),
#         )

models = {
    'gpt_4o': get_gpt_4o,
    'llama3_1_8b': get_llama3_1_8b,
    'gemma2_9b' : get_gemma2_9b,
    'finetuned_tomasonjo_llama3_1_8b' : get_finetuned_tomasonjo_llama3_1_8b,
    'finetuned_gemma2_9b':get_finetuned_gemma2_9b,
    'finetuned_azzedde_llama3_1_8b':get_finetuned_azzedde_llama3_1_8b,
    'finetuned_gemma2_9b_local':get_finetuned_gemma2_9b_local,
    'qwen2_5_7b':get_qwen2_5_7b,
    'llama3_2_3b':get_llama3_2_3b,
    'qwen2_5_Coder_32b': get_qwen2_5_Coder_32b,
    'qwen2_5_72b':get_qwen2_5_72b,
    'llama3_2_3b_local': get_llama3_2_3b_local
}