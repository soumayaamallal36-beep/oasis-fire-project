import pytest
import numpy as np
from src.models.ensemble import EnsembleModel

def test_ensemble_initialization():
    model = EnsembleModel()
    assert model.best_model is None
    assert model.voting_model is None
    assert model.stacking_model is None

def test_predict_risk_level_without_model():
    model = EnsembleModel()
    with pytest.raises(ValueError):
        model.predict_risk_level({"temperature": 35})

def test_fwi_calculation_in_satellite_collector():
    from src.data_collection.satellite_collector import SatelliteCollector
    fwi = SatelliteCollector.calculate_fwi(38.0, 15.0, 25.0, 0.0)
    assert isinstance(fwi, float)
    assert fwi >= 0
