"""Machine Learning Engine for Multi-Hazard Risk Prediction.

Trains & executes ML models for:
1. Landslide Susceptibility (XGBoost / RandomForestClassifier)
2. Flood Inundation Depth (RandomForestRegressor)
3. Population Casualty & Evacuation Vulnerability Triage (LightGBM / RandomForestClassifier)
"""

from pathlib import Path
from typing import Dict, Any
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.model_selection import train_test_split

try:
    from xgboost import XGBClassifier
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False

try:
    from lightgbm import LGBMClassifier
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False

from .data.dataset_generator import generate_and_save_all_datasets

MODELS_DIR = Path(__file__).parent / "models"
DATA_DIR = Path(__file__).parent / "data"

LANDSLIDE_MODEL_PATH = MODELS_DIR / "landslide_susceptibility_model.joblib"
FLOOD_MODEL_PATH = MODELS_DIR / "flood_depth_model.joblib"
TRIAGE_MODEL_PATH = MODELS_DIR / "vulnerability_triage_model.joblib"

TRIAGE_LABELS = {0: "Low", 1: "Moderate", 2: "High", 3: "Critical"}

# Cache loaded models in memory for fast API inference
_LOADED_MODELS: Dict[str, Any] = {}


def ensure_datasets_exist() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ls_file = DATA_DIR / "landslide_susceptibility_dataset.csv"
    fl_file = DATA_DIR / "flood_depth_dataset.csv"
    vuln_file = DATA_DIR / "population_vulnerability_dataset.csv"

    if not (ls_file.exists() and fl_file.exists() and vuln_file.exists()):
        generate_and_save_all_datasets()


def train_landslide_model() -> Dict[str, Any]:
    ensure_datasets_exist()
    df = pd.read_csv(DATA_DIR / "landslide_susceptibility_dataset.csv", on_bad_lines="skip")

    feature_cols = [
        "slope_deg",
        "elevation_m",
        "curvature",
        "soil_ksat_mm_h",
        "clay_pct",
        "historical_density_norm",
        "rainfall_24h_mm",
        "rainfall_7d_mm",
    ]
    X = df[feature_cols]
    y = df["landslide_occurred"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    if HAS_XGBOOST:
        model = XGBClassifier(n_estimators=100, max_depth=5, learning_rate=0.08, random_state=42)
    else:
        model = RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42)

    model.fit(X_train, y_train)
    acc = float(model.score(X_test, y_test))

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "features": feature_cols}, LANDSLIDE_MODEL_PATH)
    _LOADED_MODELS["landslide"] = {"model": model, "features": feature_cols}
    return {"model_name": "Landslide Susceptibility", "accuracy": round(acc, 4)}


def train_flood_model() -> Dict[str, Any]:
    ensure_datasets_exist()
    df = pd.read_csv(DATA_DIR / "flood_depth_dataset.csv", on_bad_lines="skip")

    feature_cols = [
        "elevation_m",
        "dist_to_river_m",
        "catchment_area_ha",
        "rainfall_24h_mm",
        "rainfall_7d_mm",
        "slope_deg",
    ]
    X = df[feature_cols]
    y = df["flood_depth_m"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = RandomForestRegressor(n_estimators=100, max_depth=6, random_state=42)
    model.fit(X_train, y_train)
    r2 = float(model.score(X_test, y_test))

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "features": feature_cols}, FLOOD_MODEL_PATH)
    _LOADED_MODELS["flood"] = {"model": model, "features": feature_cols}
    return {"model_name": "Flood Depth Regressor", "r2_score": round(r2, 4)}


def train_triage_model() -> Dict[str, Any]:
    ensure_datasets_exist()
    df = pd.read_csv(DATA_DIR / "population_vulnerability_dataset.csv", on_bad_lines="skip")

    feature_cols = [
        "pop_density_per_km2",
        "vulnerable_age_ratio",
        "shelter_dist_km",
        "landslide_susceptibility",
        "flood_depth_m",
        "housing_durability_idx",
    ]
    X = df[feature_cols]
    y = df["triage_level"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    if HAS_LIGHTGBM:
        model = LGBMClassifier(n_estimators=80, max_depth=4, learning_rate=0.05, random_state=42, verbose=-1)
    else:
        model = RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42)

    model.fit(X_train, y_train)
    acc = float(model.score(X_test, y_test))

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "features": feature_cols}, TRIAGE_MODEL_PATH)
    _LOADED_MODELS["triage"] = {"model": model, "features": feature_cols}
    return {"model_name": "Evacuation Triage", "accuracy": round(acc, 4)}


def train_all_models() -> Dict[str, Any]:
    res_ls = train_landslide_model()
    res_fl = train_flood_model()
    res_tr = train_triage_model()
    return {"landslide": res_ls, "flood": res_fl, "triage": res_tr}


def _get_model(key: str, path: Path, train_func) -> Any:
    if key in _LOADED_MODELS:
        return _LOADED_MODELS[key]
    if path.exists():
        loaded = joblib.load(path)
        _LOADED_MODELS[key] = loaded
        return loaded
    train_func()
    return _LOADED_MODELS[key]


def predict_landslide_susceptibility(input_features: Dict[str, float]) -> float:
    container = _get_model("landslide", LANDSLIDE_MODEL_PATH, train_landslide_model)
    model = container["model"]
    features = container["features"]

    row = pd.DataFrame([{col: input_features.get(col, 0.0) for col in features}])
    if hasattr(model, "predict_proba"):
        prob = model.predict_proba(row)[0][1]
    else:
        prob = model.predict(row)[0]
    return round(float(prob), 4)


def predict_flood_depth(input_features: Dict[str, float]) -> float:
    container = _get_model("flood", FLOOD_MODEL_PATH, train_flood_model)
    model = container["model"]
    features = container["features"]

    row = pd.DataFrame([{col: input_features.get(col, 0.0) for col in features}])
    pred = model.predict(row)[0]
    return round(max(float(pred), 0.0), 2)


def predict_population_triage(input_features: Dict[str, float]) -> Dict[str, Any]:
    container = _get_model("triage", TRIAGE_MODEL_PATH, train_triage_model)
    model = container["model"]
    features = container["features"]

    row = pd.DataFrame([{col: input_features.get(col, 0.0) for col in features}])
    pred_class = int(model.predict(row)[0])
    label = TRIAGE_LABELS.get(pred_class, "Moderate")

    return {"class_id": pred_class, "triage_level": label}
