import pandas as pd
import numpy as np
import uuid
from pathlib import Path

def generate_correlated_chargebacks(n_samples: int = 25000) -> pd.DataFrame:
    """
    Generates a mathematically correlated synthetic dataset for CatBoost training.
    
    PITCH/README JUSTIFICATION:
    Since real Razorpay transaction data is highly confidential, we mathematically 
    simulated a dataset of 25,000 disputes. The generation logic enforces real-world 
    fraud vectors (e.g., account age correlates with chargeback rate; EXIF-stripping 
    correlates with VLM contradictions).
    """
    np.random.seed(42)
    
    # 1. Base Identifiers & Categories
    data = {
        "transaction_id": [f"pay_{uuid.uuid4().hex[:14]}" for _ in range(n_samples)],
        # Using exact required reason codes
        "reason_code": np.random.choice(['fraud', 'not_received', 'damaged'], n_samples, p=[0.4, 0.4, 0.2]),
        "merchant_category": np.random.choice(['electronics', 'apparel', 'digital_services'], n_samples, p=[0.4, 0.4, 0.2])
    }
    df = pd.DataFrame(data)

    # 2. Define the "Hidden Fraudster" Profile
    # In reality, about 15-20% of disputes might be coordinated or friendly fraud.
    is_fraudster = np.random.choice([True, False], n_samples, p=[0.18, 0.82])
    
    # Correlate account age and prior chargebacks to the fraudster profile
    df['user_account_age_days'] = np.where(
        is_fraudster, 
        np.random.randint(1, 14, n_samples),     # Burner accounts
        np.random.randint(30, 1500, n_samples)   # Established accounts
    )
    
    df['prior_chargeback_count'] = np.where(
        is_fraudster, 
        np.random.randint(2, 7, n_samples),      # Serial offenders
        np.random.choice([0, 1, 2], n_samples, p=[0.85, 0.10, 0.05]) # Normal users
    )

    # 3. Transaction Amount logic
    # Electronics are high-target, high-value items
    df['transaction_amount'] = np.where(
        df['merchant_category'] == 'electronics',
        np.random.normal(25000, 5000, n_samples),  # ₹25k avg
        np.random.normal(3000, 1000, n_samples)    # ₹3k avg
    ).clip(min=100).round(2)

    # 4. Perception Engine Simulation (The core of Layer 1)
    # Fraudsters are highly likely to submit EXIF-stripped images (screenshots)
    df['metadata_match'] = np.where(
        is_fraudster, 
        np.random.choice([True, False], n_samples, p=[0.05, 0.95]), # 95% stripped/mismatched
        np.random.choice([True, False], n_samples, p=[0.85, 0.15])  # 85% intact/matched
    )
    
    # Fraudsters claiming "damaged" usually have images that contradict the claim
    df['vlm_contradiction_found'] = np.where(
        is_fraudster,
        np.random.choice([True, False], n_samples, p=[0.80, 0.20]), # VLM catches them 80% of the time
        np.random.choice([True, False], n_samples, p=[0.05, 0.95])  # 5% false positive rate for normal users
    )

    # 5. Target Label Generation (Historical Win)
    def calculate_win(row):
        score = 0.0
        
        # Heaviest weight given to the Agentic Perception Layer
        if row['vlm_contradiction_found']: score += 0.55
        if row['metadata_match']: score += 0.35
        
        # Risk factors (Stat Gatekeeper logic)
        if row['prior_chargeback_count'] > 2: score += 0.15
        if row['user_account_age_days'] < 14: score -= 0.10
        
        # Specific interaction: if the claim is "damaged", VLM contradiction is the ultimate decider
        if row['reason_code'] == 'damaged' and row['vlm_contradiction_found']:
            score += 0.25
            
        # Introduce Gaussian noise so the model has to learn probabilities, not hard rules
        noise = np.random.normal(0, 0.12)
        
        # A score > 0.60 (plus noise) represents a historical win (1) for the merchant
        return 1 if (score + noise) >= 0.60 else 0

    df['historical_win'] = df.apply(calculate_win, axis=1)
    return df

if __name__ == "__main__":
    df = generate_correlated_chargebacks(25000)
    
    # Save relative to the script location
    output_path = Path(__file__).parent / "synthetic_chargeback_data.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    
    print(f"Generated {len(df)} correlated samples.")
    print("\nTarget Variable Distribution:")
    print(df['historical_win'].value_counts(normalize=True).round(3))