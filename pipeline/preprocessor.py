import re
from typing import List

# We are removing spacy to avoid the torch DLL initialization error
# which occurs on this system when loading spacy's dependencies.

def clean_text(text: str) -> str:
    """
    Basic text cleaning: lowercase, remove punctuation, strip whitespace
    """
    if not text:
        return ""
    
    # Lowercase
    text = text.lower().strip()
    
    # Remove punctuation
    text = re.sub(r'[^\w\s]', '', text)
    
    # Normalize Arabic (basic)
    text = re.sub(r'[أإآ]', 'ا', text)
    text = re.sub(r'ة', 'ه', text)
    text = re.sub(r'ى', 'ي', text)
    
    return text

def preprocess(text: str) -> str:
    """
    Simple preprocessing: cleaning + whitespace tokenization
    (Alternative to spacy to avoid torch error)
    """
    text = clean_text(text)
    
    # Reduced stopword set - keep domain-specific words like أحمد, احمد
    # Only remove very common function words that don't affect intent
    stopwords = {'في', 'على', 'هو', 'هي', 'is', 'the', 'a', 'an', 'of', 'in', 'on', 'to', 'for'}
    
    tokens = text.split()
    tokens = [t for t in tokens if t not in stopwords]
    
    return " ".join(tokens)

if __name__ == "__main__":
    test_texts = [
        "من غاب اليوم؟",
        "Show me the grades for Ahmed!",
        "درجاتي في الرياضيات"
    ]
    for t in test_texts:
        print(f"Original: {t} -> Preprocessed: {preprocess(t)}")
