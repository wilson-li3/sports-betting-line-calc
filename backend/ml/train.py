"""
Model training with LogisticRegression baseline.
Uses Pipeline with StandardScaler and SimpleImputer.
"""
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.compose import ColumnTransformer
from sklearn.calibration import CalibratedClassifierCV
from sklearn.isotonic import IsotonicRegression


def train_model(X_train, y_train, C=None, max_iter=None):
    """
    Train a LogisticRegression model with preprocessing pipeline.
    
    Args:
        X_train: Training features (DataFrame)
        y_train: Training labels (Series)
        C: Regularization strength (defaults to config)
        max_iter: Maximum iterations (defaults to config)
        
    Returns:
        Fitted pipeline model
    """
    from .config import LOGISTIC_C, LOGISTIC_MAX_ITER
    
    if C is None:
        C = LOGISTIC_C
    if max_iter is None:
        max_iter = LOGISTIC_MAX_ITER
    
    # Task 1: Confirm numeric features are standardized and imputed
    # Get numeric columns
    numeric_cols = X_train.select_dtypes(include=[np.number]).columns.tolist()
    
    # Create preprocessing pipeline for numeric features
    # StandardScaler ensures proper scaling, SimpleImputer handles missing values
    numeric_transformer = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    
    # Column transformer (we only have numeric features for now)
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, numeric_cols),
        ],
        remainder="drop",  # Drop any non-numeric columns
    )
    
    # Full pipeline: preprocess + model
    # Task 1: Increase max_iter, add C parameter
    pipeline = Pipeline(steps=[
        ("preprocessor", preprocessor),
        ("classifier", LogisticRegression(
            C=C,
            max_iter=max_iter,
            random_state=42,
            solver="lbfgs",
        )),
    ])
    
    # Fit pipeline
    pipeline.fit(X_train, y_train)
    
    return pipeline


def train_calibrated_model(base_model, X_cal, y_cal, method="sigmoid"):
    """
    Task 2: Fit a calibrated classifier using calibration data.
    
    Uses manual calibration (Platt scaling for sigmoid, isotonic regression for isotonic)
    since cv="prefit" may not work in all sklearn versions.
    
    Args:
        base_model: Pre-fitted base model
        X_cal: Calibration features (DataFrame)
        y_cal: Calibration labels (Series)
        method: Calibration method ("sigmoid" or "isotonic")
        
    Returns:
        Calibrated model wrapper that implements predict_proba
    """
    from sklearn.linear_model import LogisticRegression as LogReg
    
    # Get uncalibrated predictions from base model
    proba_cal = base_model.predict_proba(X_cal)[:, 1]
    
    if method == "sigmoid":
        # Platt scaling: fit logistic regression to transform probabilities
        # Reshape for sklearn
        proba_cal_2d = proba_cal.reshape(-1, 1)
        cal_model = LogReg()
        cal_model.fit(proba_cal_2d, y_cal)
        
        # Create a wrapper that applies calibration during predict_proba
        class CalibratedWrapper:
            def __init__(self, base_model, cal_model):
                self.base_model = base_model
                self.cal_model = cal_model
            
            def predict_proba(self, X):
                proba = self.base_model.predict_proba(X)[:, 1].reshape(-1, 1)
                calibrated_proba = self.cal_model.predict_proba(proba)[:, 1]
                # Return in shape [n_samples, 2]
                return np.column_stack([1 - calibrated_proba, calibrated_proba])
        
        return CalibratedWrapper(base_model, cal_model)
    
    elif method == "isotonic":
        # Isotonic regression
        isotonic = IsotonicRegression(out_of_bounds="clip")
        isotonic.fit(proba_cal, y_cal)
        
        class CalibratedWrapper:
            def __init__(self, base_model, isotonic):
                self.base_model = base_model
                self.isotonic = isotonic
            
            def predict_proba(self, X):
                proba = self.base_model.predict_proba(X)[:, 1]
                calibrated_proba = self.isotonic.predict(proba)
                # Ensure probabilities are in [0, 1]
                calibrated_proba = np.clip(calibrated_proba, 0, 1)
                # Return in shape [n_samples, 2]
                return np.column_stack([1 - calibrated_proba, calibrated_proba])
        
        return CalibratedWrapper(base_model, isotonic)
    
    else:
        raise ValueError(f"Unknown calibration method: {method}")


def predict_proba(model, X_test):
    """
    Predict probabilities for test set.
    
    Args:
        model: Fitted pipeline model or CalibratedClassifierCV
        X_test: Test features (DataFrame)
        
    Returns:
        Array of predicted probabilities (shape: [n_samples, 2])
        Use [:, 1] for P(y=1) predictions
    """
    proba = model.predict_proba(X_test)
    return proba
