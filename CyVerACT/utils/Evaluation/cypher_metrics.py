from nltk.translate.bleu_score import sentence_bleu
import textdistance
import regex as re
from typing import Set
from rouge_score import rouge_scorer


##################################################
########### Format function for Rouge,bleu #######
##################################################
def format_rouge_bleu(query):
    ''' Formats Cypher queries by adding whitespaces before and after
    #  (, ) , : of nodes 
    #  {, }, . of their properties
    # [ , ],  - , ->, <- for realtionships
    # comma
    # multiply and dieresis * / 
    # > or < 

    It is used by ROUGE and bleu
    '''
    pattern = r'(\(|\)|:|\{|\}|->|<-|-|\[|\]|,|\.|\*|\/|<|>)'
    
    # Replace each occurrence of the keyword with the keyword and a space before and after it
    formatted_query = re.sub(pattern, r' \1 ', query)
    # Normalize spaces and remove any extra leading/trailing spaces
    formatted_query = re.sub(r'\s+', ' ', formatted_query).strip()
    return formatted_query

###########################################
########### Rouge-L #######################
###########################################
def rougeL_score(original_cypher: str, generated_cypher: str):
    hypothesis = generated_cypher
    reference = original_cypher
    #calculate rouge -l score
    scorer = rouge_scorer.RougeScorer(['rougeL'], use_stemmer=True)
    scores = scorer.score(format_rouge_bleu(reference), format_rouge_bleu(hypothesis))['rougeL']
    precision = round(scores[0],2)
    recall = round(scores[1],2)
    f1 = round(scores[2],2)
    return precision, recall, f1

###########################################
########### Bleu score ####################
###########################################
def bleu_score (original_cypher: str, generated_cypher: str) -> float:

    hypothesis = generated_cypher
    reference = original_cypher
    # Returns bleu score 
    reference_list = format_rouge_bleu(reference).split()
    candidate_list = format_rouge_bleu(hypothesis).split()
    return sentence_bleu([reference_list], candidate_list)

############################################################
########### Format function for Jaccard,Jaro-Winkler #######
############################################################

def add_whitspaces_remove_special_characters(query,sub=False):
    pattern = r'(\(|\)|:|\{|\}|->|<-|-|\[|\]|,|\.|\*|\/|<|>)'
    
    # Replace each occurrence of the keyword with the keyword and a space before and after it
    formatted_query = re.sub(pattern, r' \1 ', query)
    
    if sub:
       # Replace each occurrence of the keyword with the keyword and a space before and after it
        formatted_query = re.sub(pattern, ' ', formatted_query)
    # Normalize spaces and remove any extra leading/trailing spaces
    formatted_query = re.sub(r'\s+', ' ', formatted_query).strip()
    return formatted_query

def upper_neo4j_keywords(query):

    keywords = ['MATCH', 'WHERE', 'RETURN', 'OPTIONAL', 'MERGE', 'DELETE', 'CREATE', 
                'ORDER BY', 'LIMIT', 'COUNT', 'DISTINCT', 'EXISTS', 'IN', 'AND', 'OR','MIN', 'MAX', 'AVG',
                'UNWIND', 'WITH',  'SET', 'MERGE', 'REMOVE', 'FILTER', 'COLLECT', 'AS', 'FOREACH', 'REDUCE', 'CASE',
                'toFloat', 'NOT', 'NULL', 'THEN', 'ELSE', 'END', 'TRUE', 'FALSE', 'DESC', 'ASC' , 'IS', 'NULL', 'WHEN', 'SIZE']

    # Define the pattern with word boundaries to match whole keywords only
    pattern = r'\b(' + '|'.join(keywords) + r')\b'
    
    # Replace each keyword with its lowercase equivalent
    modified_query = re.sub(pattern, lambda x: x.group(0).upper(), query,flags=re.IGNORECASE)
    return modified_query

def format_jaccard_jaro(query,sub=False):

    #returns formatted qurty with whitespaces where needed
    query_wt_keywords_extra_wtspaces = add_whitspaces_remove_special_characters(query,sub)
    characters_format = upper_neo4j_keywords(query_wt_keywords_extra_wtspaces)
    return characters_format

#######################################################################
########### Jaccard similarity cypher (word based) ####################
#######################################################################
def jaccard_formula(setL: Set, setR: Set) -> float:
    """
    Calculate the similarity between two sets using Jaccard index formula.
    """
    return len(setL.intersection(setR)) / len(setL.union(setR))


def jaccard_similarity_cypher(original_cypher: str, generated_cypher: str) -> float:
    """
    Calculate the jaccard index between the original and the generated cypher query based on words.
    """
    words_original = format_jaccard_jaro(original_cypher,sub=True).split()
    words_generated = format_jaccard_jaro(generated_cypher,sub=True).split()

    return jaccard_formula(set(words_original),set(words_generated))

#######################################################################
########### Jaro-winkler similarity cypher (character based) ##########
#######################################################################

def jaro_winkler_cypher(original_cypher: str, generated_cypher: str) -> float:
    """
    Calculate the Jaro-Winkler distance between two strings.

    The Jaro-Winkler distance is a measure of similarity between two strings.
    The score is normalized such that 0 equates to no similarity and
    1 is an exact match.
    """
    return textdistance.jaro_winkler(format_jaccard_jaro(original_cypher), format_jaccard_jaro(generated_cypher))

