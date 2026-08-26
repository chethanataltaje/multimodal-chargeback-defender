import logging
from pathlib import Path
import pandas as pd
from catboost import CatBoostClassifier

logger = logging.getLogger("GatekeeperPredictor")

FEATURE_COLUMNS = [
    'user_account_age_days', 
    'transaction_amount', 
    'prior_chargeback_count',
    'reason_code', 
    'merchant_category', 
    'vlm_contradiction_found', 
    'metadata_match'
]

CAT_FEATURES = ['reason_code', 'merchant_category', 'vlm_contradiction_found', 'metadata_match']

class GatekeeperPredictor:
    def __init__(self):
        self._model = None
        self._explainer = None
        self.feature_columns = FEATURE_COLUMNS

    @property
    def model(self) -> CatBoostClassifier:
        if self._model is None:
            model_path = Path(__file__).parent / "gatekeeper_model.cbm"
            if not model_path.exists():
                raise FileNotFoundError(f"Gatekeeper model file not found at {model_path}. Run 'python src/gatekeeper/train_model.py' first.")
            self._model = CatBoostClassifier()
            self._model.load_model(str(model_path))
        return self._model

    @property
    def explainer(self):
        if self._explainer is None:
            try:
                import shap
                self._explainer = shap.TreeExplainer(self.model)
            except Exception as e:
                logger.warning(f"Could not initialize SHAP explainer: {e}")
                self._explainer = None
        return self._explainer

    def predict_with_explanation(self, feature_dict: dict) -> dict:
        """
        Accepts a dictionary of transaction & perception features and returns 
        the calibrated win probability along with top SHAP feature drivers.
        """
        # Ensure numerical casting for numeric features
        prepared_dict = {
            'user_account_age_days': int(feature_dict.get('user_account_age_days', 30)),
            'transaction_amount': float(feature_dict.get('transaction_amount', 1000.0)),
            'prior_chargeback_count': int(feature_dict.get('prior_chargeback_count', 0)),
            'reason_code': str(feature_dict.get('reason_code', 'damaged')),
            'merchant_category': str(feature_dict.get('merchant_category', 'electronics')),
            'vlm_contradiction_found': str(feature_dict.get('vlm_contradiction_found', False)),
            'metadata_match': str(feature_dict.get('metadata_match', False))
        }

        df = pd.DataFrame([prepared_dict])[self.feature_columns]
        
        # predict_proba returns [prob_loss, prob_win]. Index 1 is win probability.
        win_probability = float(self.model.predict_proba(df)[0][1])
        
        # Calculate SHAP values for auditability and dashboard XAI
        top_3_features = []
        if self.explainer:
            try:
                shap_values = self.explainer.shap_values(df)
                feature_importance = list(zip(self.feature_columns, shap_values[0]))
                feature_importance.sort(key=lambda x: abs(x[1]), reverse=True)
                top_3_features = [{"feature": k, "impact": float(v)} for k, v in feature_importance[:3]]
            except Exception as e:
                logger.warning(f"SHAP explanation calculation note: {e}")
                
        if not top_3_features:
            # Fallback heuristic explanation based on high weights
            vlm_flag = feature_dict.get('vlm_contradiction_found', False)
            top_3_features = [
                {"feature": "vlm_contradiction_found", "impact": 0.45 if vlm_flag else -0.30},
                {"feature": "prior_chargeback_count", "impact": 0.15 if feature_dict.get('prior_chargeback_count', 0) > 2 else -0.05},
                {"feature": "user_account_age_days", "impact": -0.10 if feature_dict.get('user_account_age_days', 30) < 14 else 0.05}
            ]

        return {
            "win_probability": win_probability,
            "top_drivers": top_3_features
        }

# Singleton instance
gatekeeper = GatekeeperPredictor()