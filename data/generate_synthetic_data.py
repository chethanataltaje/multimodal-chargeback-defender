import pandas as pd
import numpy as np
import uuid
from pathlib import Path

def generate_chargeback_data(n_samples: int = 100) -> pd.DataFrame:
    """
    Generates synthetic tabular data for the ML Gatekeeper (CatBoost).
    """
    np.random.seed(42)
    
    # 1. Base Features
    data = {
        "transaction_id": [str(uuid.uuid4()) for _ in range(n_samples)],
        "user_account_age_days": np.random.randint(1, 2000, n_samples),
        "transaction_amount": np.round(np.random.uniform(15.0, 3500.0, n_samples), 2),
        "prior_chargeback_count": np.random.randint(0, 6, n_samples),
        
        # Categorical Features (To be passed natively to CatBoost)
        "reason_code": np.random.choice(['fraud', 'not_received', 'damaged'], n_samples),
        "merchant_category": np.random.choice(['electronics', 'apparel', 'digital_services', 'home_goods'], n_samples),
        
        # Perception Engine Mock Outputs
        "vlm_contradiction_found": np.random.choice([True, False], n_samples, p=[0.25, 0.75]),
        "metadata_match": np.random.choice([True, False], n_samples, p=[0.60, 0.40])
    }
    
    df = pd.DataFrame(data)
    
    # 2. Target Variable Generation (historical_win)
    # We simulate real-world risk weighting so the CatBoost model learns actual patterns.
    def calculate_win_probability(row):
        score = 0.0
        
        # Strongest signal: LLM found a visual contradiction in the evidence
        if row['vlm_contradiction_found']:
            score += 0.60
            
        # Good signal: ExifRead/GPS data matches the delivery log
        if row['metadata_match']:
            score += 0.30
            
        # Risk factors
        if row['prior_chargeback_count'] > 2:
            score += 0.20  # Serial returners are easier to beat in disputes
            
        if row['user_account_age_days'] < 30 and row['reason_code'] == 'fraud':
            score -= 0.30  # Harder to win fraud claims on brand new accounts
            
        # Add slight random noise to prevent a perfect decision tree
        noise = np.random.uniform(-0.1, 0.1)
        final_prob = max(0.0, min(1.0, score + noise))
        
        # Threshold for a win (1 = merchant won dispute, 0 = lost)
        return 1 if final_prob >= 0.55 else 0

    df['historical_win'] = df.apply(calculate_win_probability, axis=1)
    
    return df

if __name__ == "__main__":
    print("Generating synthetic dispute data...")
    df = generate_chargeback_data(100)
    
    # Ensure data directory exists
    output_dir = Path(__file__).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = output_dir / "synthetic_chargeback_data.csv"
    df.to_csv(output_path, index=False)
    
    print(f"Success! {len(df)} rows generated at {output_path}")
    print("\nSample Data Preview:")
    print(df[['reason_code', 'vlm_contradiction_found', 'prior_chargeback_count', 'historical_win']].head())