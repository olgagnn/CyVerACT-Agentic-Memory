import re
from nltk.corpus import stopwords
'''
Functions for NLP tasks (e.g., text preprocessing) in questions and KG schema terms to calculate embeddings and find similarities.
'''

def preprocess_text(question:str) -> str:
        """Preprocess the text by removing special characters, converting to lowercase, and removing stopwords."""
        # Remove all the special characters and numbers
        question = re.sub(r'[^a-zA-Z\s]', ' ', str(question))
        # Converting to Lowercase
        question = question.lower()
        # Split into words
        tokens = question.split()
        #Remove stopwords
        stopWords = set(stopwords.words('english')) #a, and, the , be , your , ...
        tokens = [word for word in tokens if word not in stopWords]

        preprocessed_text = ' '.join(tokens)

        return preprocessed_text


def split_camel_case(s:str) -> list[str]:
    """Split camelCase or PascalCase into individual words. (FOR LABELS)"""
    return re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?![a-z])', s)


def split_by_underscore(s:str) -> list[str]:
    """Split snake_case into individual words.(for relationship types)"""
    return s.split('_')