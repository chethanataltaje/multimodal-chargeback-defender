import pandas as pd
import shap
from pathlib import Path
from catboost import CatBoostClassifier

class GatekeeperPredictor:
    def __init__(self):
        self.model = CatBoostClassifier()
        model_path = Path(__file__).parent / "gatekeeper_model.cbm"
        
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found at {model_path}. Run train_model.py first.")
            
        self.model.load_model(str(model_path))
        
        # Must match the training pipeline's exact column order
        self.feature_columns = [
            'user_account_age_days', 
            'transaction_amount', 
            'prior_chargeback_count',
            'reason_code', 
            'merchant_category', 
            'vlm_contradiction_found', 
            'metadata_match'
        ]
        
        # Initialize SHAP explainer for the dashboard
        self.explainer = shap.TreeExplainer(self.model)

    def predict_with_explanation(self, feature_dict: dict) -> dict:
        """
        Accepts a dictionary of transaction & perception data and returns 
        the probability of winning the dispute along with SHAP explanations.
        """
        # Convert dictionary to DataFrame to ensure shape and type compliance
        df = pd.DataFrame([feature_dict])
        
        # Cast categorical features to strings as expected by the compiled model
        cat_features = ['reason_code', 'merchant_category', 'vlm_contradiction_found', 'metadata_match']
        for col in cat_features:
            if col in df.columns:
                df[col] = df[col].astype(str)
                
        # Ensure exact column order
        df = df[self.feature_columns]
        
        # predict_proba returns an array of [prob_loss, prob_win]. We want index 1.
        win_probability = float(self.model.predict_proba(df)[0][1])
        
        # Calculate SHAP values for auditability
        shap_values = self.explainer.shap_values(df)
        
        # Zip feature names with their absolute SHAP values to find top 3 drivers
        feature_importance = list(zip(self.feature_columns, shap_values[0]))
        # Sort by absolute impact magnitude
        feature_importance.sort(key=lambda x: abs(x[1]), reverse=True)
        
        top_3_features = [{"feature": k, "impact": float(v)} for k, v in feature_importance[:3]]
        
        return {
            "win_probability": win_probability,
            "top_drivers": top_3_features
        }

# Singleton instance to be imported by the LangGraph orchestrator
gatekeeper = GatekeeperPredictor()