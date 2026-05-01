from sklearn.feature_extraction.text import TfidfVectorizer
import joblib
import os
import numpy as np
from typing import List, Union

class Embedder:
    def __init__(self, model_dir: str = "models"):
        """
        Initialize a TF-IDF vectorizer as a lightweight alternative to MiniLM.
        """
        self.model_dir = model_dir
        self.vectorizer_path = os.path.join(model_dir, "tfidf_vectorizer.pkl")
        self.vectorizer = None

    def train(self, texts: List[str]):
        """
        Train the TF-IDF vectorizer on the dataset.
        """
        print("Training TF-IDF vectorizer...")
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2), # Use unigrams and bigrams
            max_features=1000,
            sublinear_tf=True
        )
        self.vectorizer.fit(texts)
        
        if not os.path.exists(self.model_dir):
            os.makedirs(self.model_dir)
        joblib.dump(self.vectorizer, self.vectorizer_path)
        print(f"Vectorizer saved to {self.vectorizer_path}")

    def load(self):
        if not os.path.exists(self.vectorizer_path):
            raise FileNotFoundError("Vectorizer model not found.")
        self.vectorizer = joblib.load(self.vectorizer_path)
        print("TF-IDF vectorizer loaded.")

    def encode(self, texts: Union[str, List[str]]) -> np.ndarray:
        """
        Convert text into TF-IDF vectors.
        """
        if self.vectorizer is None:
            self.load()
            
        if isinstance(texts, str):
            texts = [texts]
        
        return self.vectorizer.transform(texts).toarray()

if __name__ == "__main__":
    # Test
    emb = Embedder()
    try:
        emb.load()
        print("Shape:", emb.encode("test").shape)
    except:
        print("Please train first.")
