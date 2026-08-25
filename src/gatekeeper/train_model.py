import pandas as pd
from pathlib import Path
from catboost import CatBoostClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score

def train_gatekeeper():
    # 1. Load Data
    data_path = Path(__file__).parent.parent.parent / "data" / "synthetic_chargeback_data.csv"
    print(f"Loading data from {data_path}...")
    df = pd.read_csv(data_path)

    # 2. Prepare Features and Target
    # We drop transaction_id as it has no predictive value
    X = df.drop(columns=['transaction_id', 'historical_win'])
    y = df['historical_win']

    # Identify categorical features for CatBoost
    # Booleans are cast to strings to ensure clean categorical processing
    cat_features = ['reason_code', 'merchant_category', 'vlm_contradiction_found', 'metadata_match']
    for col in cat_features:
        X[col] = X[col].astype(str)

    # 3. Train/Test Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # 4. Initialize and Train CatBoost
    print("Training CatBoost Classifier...")
    model = CatBoostClassifier(
        iterations=300, # Increased slightly for the 25k dataset
        learning_rate=0.1,
        depth=4,
        cat_features=cat_features,
        eval_metric='AUC',
        auto_class_weights='Balanced', # CRITICAL: Handles the 87/13 imbalance
        verbose=50,
        random_seed=42
    )

    model.fit(X_train, y_train, eval_set=(X_test, y_test))

    # 5. Evaluate Model
    preds = model.predict(X_test)
    probs = model.predict_proba(X_test)[:, 1]
    
    print("\n--- Model Evaluation ---")
    print(classification_report(y_test, preds))
    print(f"ROC AUC Score: {roc_auc_score(y_test, probs):.4f}")

    # 6. Save Model
    model_dir = Path(__file__).parent
    model_path = model_dir / "gatekeeper_model.cbm"
    model.save_model(str(model_path))
    print(f"\nModel saved successfully to {model_path}")

if __name__ == "__main__":
    train_gatekeeper()