import numpy as np
import joblib
import os
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder
from pipeline.preprocessor import preprocess
from pipeline.embedder import Embedder

class IntentClassifier:
    def __init__(self, model_dir: str = "models"):
        self.model_dir = model_dir
        self.model_path = os.path.join(model_dir, "intent_classifier.pkl")
        self.label_encoder_path = os.path.join(model_dir, "label_encoder.pkl")
        self.classifier = None
        self.label_encoder = None
        self.embedder = Embedder(model_dir)

    def train(self, dataset_path: str = "data/dataset.csv"):
        import pandas as pd
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import classification_report
        print(f"Loading dataset from {dataset_path}...")
        df = pd.read_csv(dataset_path)
        
        print("Preprocessing texts...")
        df['processed_text'] = df['text'].apply(preprocess)
        
        # Train the vectorizer first
        self.embedder.train(df['processed_text'].tolist())
        X = self.embedder.encode(df['processed_text'].tolist())
        
        print("Encoding labels...")
        self.label_encoder = LabelEncoder()
        y = self.label_encoder.fit_transform(df['intent'])
        
        # Use stratify=y to ensure all classes are present in both train and test sets
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
        
        print("Training Logistic Regression classifier...")
        self.classifier = LogisticRegression(
            C=5.0,
            max_iter=1000,
            random_state=42,
            class_weight='balanced',
            solver='lbfgs',
            multi_class='multinomial'
        )
        self.classifier.fit(X_train, y_train)
        
        print("\nEvaluation Report:")
        y_pred = self.classifier.predict(X_test)
        report = classification_report(y_test, y_pred, target_names=self.label_encoder.classes_)
        print(report)
        
        # Save models
        if not os.path.exists(self.model_dir):
            os.makedirs(self.model_dir)
            
        joblib.dump(self.classifier, self.model_path)
        joblib.dump(self.label_encoder, self.label_encoder_path)
        print(f"\nModels saved to {self.model_dir}/")

    def load(self):
        if not os.path.exists(self.model_path) or not os.path.exists(self.label_encoder_path):
            raise FileNotFoundError("Model files not found. Please train the model first.")
            
        self.classifier = joblib.load(self.model_path)
        self.label_encoder = joblib.load(self.label_encoder_path)
        self.embedder.load()
        print("Intent classifier loaded.")

    def predict(self, text: str):
        if self.classifier is None:
            self.load()
            
        processed = preprocess(text)
        embedding = self.embedder.encode(processed)
        
        probabilities = self.classifier.predict_proba(embedding)[0]
        
        max_idx = np.argmax(probabilities)
        intent = self.label_encoder.classes_[max_idx]
        confidence = probabilities[max_idx]
        
        return intent, confidence

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", action="store_true", help="Train the model")
    args = parser.parse_args()
    
    clf = IntentClassifier()
    if args.train:
        clf.train()
    else:
        # Test prediction
        try:
            intent, conf = clf.predict("من غاب اليوم؟")
            print(f"Prediction: {intent} (Confidence: {conf:.2f})")
        except FileNotFoundError:
            print("Please run with --train first.")
