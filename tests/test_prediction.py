"""
tests/test_prediction.py
--------------------------
Tests unitaires du module de prédiction.

Usage :
    pytest tests/ -v
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.prediction.feature_engineering import (
    FEATURE_COLUMNS,
    build_features,
    prepare_input,
)


class TestFeatureEngineering:
    """Tests de la construction des features."""

    def _base_row(self):
        return {
            "temperature": 32.0,
            "humidite": 16.0,
            "precipitation": 5.0,
            "vent": 4.0,
            "pente": 5.73,
            "altitude": 1169.3,
            "exposition": 165.51,
            "ndvi_avant": 0.144,
            "mois_num": 1,
        }

    def test_build_features_returns_copy(self):
        df = pd.DataFrame([self._base_row()])
        df_out = build_features(df)
        assert df_out is not df, "build_features doit retourner une copie"

    def test_derived_columns_present(self):
        df = pd.DataFrame([self._base_row()])
        df_out = build_features(df)
        for col in ["indice_secheresse", "indice_propagation",
                    "stress_vegetal", "exposition_sud"]:
            assert col in df_out.columns, f"Colonne manquante : {col}"

    def test_indice_secheresse_positive_with_high_temp(self):
        row = self._base_row()
        row["temperature"] = 40.0
        row["humidite"] = 10.0
        row["precipitation"] = 0.1
        df = build_features(pd.DataFrame([row]))
        assert df["indice_secheresse"].iloc[0] > 0

    def test_exposition_sud_range(self):
        row = self._base_row()
        df = build_features(pd.DataFrame([row]))
        val = df["exposition_sud"].iloc[0]
        assert 0.0 <= val <= 1.0, f"Valeur hors [0, 1] : {val}"

    def test_prepare_input_returns_correct_columns(self):
        X = prepare_input(
            temperature=32, humidite=15, precipitation=2, vent=4.0
        )
        assert list(X.columns) == FEATURE_COLUMNS
        assert len(X) == 1

    def test_prepare_input_single_row(self):
        X = prepare_input(
            temperature=29, humidite=20, precipitation=3, vent=4.5,
            mois="Juin"
        )
        assert X.shape == (1, len(FEATURE_COLUMNS))
        assert X["mois_num"].iloc[0] == 0   # Juin → 0

    def test_feature_columns_count(self):
        assert len(FEATURE_COLUMNS) == 13, (
            f"Attendu 13 features, obtenu {len(FEATURE_COLUMNS)}"
        )


class TestPredictionOutput:
    """Tests de cohérence des sorties de prédiction."""

    @pytest.fixture(autouse=True)
    def _train_model(self, tmp_path, monkeypatch):
        """
        Entraîne un modèle minimal avant chaque test
        qui nécessite model_inference.
        """
        import joblib
        from sklearn.dummy import DummyClassifier
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler
        from sklearn.preprocessing import LabelEncoder
        import numpy as np

        le = LabelEncoder()
        le.classes_ = np.array(["Faible", "Moyen", "Élevé", "Très élevé"])

        clf = Pipeline([
            ("scaler", StandardScaler()),
            ("clf", DummyClassifier(strategy="most_frequent")),
        ])

        # Créer un dataset minimal pour fitter le DummyClassifier
        X_dummy = pd.DataFrame([{c: 0 for c in FEATURE_COLUMNS}] * 4)
        y_dummy = np.array([0, 1, 2, 3])
        clf.fit(X_dummy, y_dummy)

        models_dir = tmp_path / "models" / "trained"
        models_dir.mkdir(parents=True)
        joblib.dump(clf, models_dir / "model_risque_incendie.pkl")
        joblib.dump(le,  models_dir / "label_encoder.pkl")

        # Monkey-patch les chemins dans model_inference
        import src.prediction.model_inference as mi
        monkeypatch.setattr(mi, "MODEL_PATH",
                            models_dir / "model_risque_incendie.pkl")
        monkeypatch.setattr(mi, "LE_PATH",
                            models_dir / "label_encoder.pkl")
        monkeypatch.setattr(mi, "_model", None)
        monkeypatch.setattr(mi, "_le", None)

    def test_predict_returns_valid_label(self):
        from src.prediction.model_inference import predict_risque
        label, conf, probas = predict_risque(32, 16, 5, 4.0)
        classes = ["Faible", "Moyen", "Élevé", "Très élevé"]
        assert label in classes, f"Label invalide : {label}"

    def test_confiance_in_range(self):
        from src.prediction.model_inference import predict_risque
        _, conf, _ = predict_risque(32, 16, 5, 4.0)
        assert 0.0 <= conf <= 1.0

    def test_probas_sum_to_one(self):
        from src.prediction.model_inference import predict_risque
        _, _, probas = predict_risque(32, 16, 5, 4.0)
        total = sum(probas.values())
        assert abs(total - 1.0) < 1e-6, f"Somme probas ≠ 1 : {total}"

    def test_predict_batch_shape(self):
        from src.prediction.model_inference import predict_batch
        df = pd.DataFrame([
            {"temperature": 33, "humidite": 15,
             "precipitation": 1, "vent": 4.5, "mois": "Juillet"},
            {"temperature": 27, "humidite": 30,
             "precipitation": 20, "vent": 3.0, "mois": "Juin"},
        ])
        result = predict_batch(df)
        assert len(result) == 2
        assert "risque_predit" in result.columns
        assert "confiance" in result.columns
