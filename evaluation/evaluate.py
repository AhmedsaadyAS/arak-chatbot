import pandas as pd
import numpy as np
import os
import joblib
from sklearn.metrics import classification_report, confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns
from pipeline.intent_classifier import IntentClassifier

def run_evaluation():
    clf = IntentClassifier()
    try:
        clf.load()
    except FileNotFoundError:
        print("Model not found. Please train it first.")
        return

    # Load dataset
    df = pd.read_csv("data/dataset.csv")
    
    print("Evaluating model performance...")
    
    # We can use the whole dataset for a quick sanity check, 
    # but ideally we should have a separate test set
    X = clf.embedder.encode(df['text'].tolist())
    y_true = clf.label_encoder.transform(df['intent'])
    
    y_pred = clf.classifier.predict(X)
    
    report = classification_report(y_true, y_pred, target_names=clf.label_encoder.classes_)
    print("\nFinal Classification Report:")
    print(report)
    
    # Generate Confusion Matrix
    cm = confusion_matrix(y_true, y_pred)
    plt.figure(figsize=(12, 10))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                xticklabels=clf.label_encoder.classes_,
                yticklabels=clf.label_encoder.classes_)
    plt.title('Intent Classification Confusion Matrix')
    plt.ylabel('Actual Intent')
    plt.xlabel('Predicted Intent')
    
    os.makedirs("evaluation/results", exist_ok=True)
    plt.savefig("evaluation/results/confusion_matrix.png")
    print("\nConfusion matrix saved to evaluation/results/confusion_matrix.png")

if __name__ == "__main__":
    run_evaluation()
