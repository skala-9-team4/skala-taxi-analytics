"""
작성자: 이민경
작성일: 2026.08.09
파일명: ml_pipeline.py
설명: 통계 검정 결과의 한계를 극복하기 위해 전진 선택법을 활용하고, 
      HistGradientBoostingRegressor의 범주형 인코딩 이슈를 개선한 최종 파이프라인.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import joblib

def run_advanced_pipeline(df: pd.DataFrame, target_col: str):
    print(f"\n========== 타겟 변수: {target_col} ==========")
    
    scenarios = {
        "v1_distance(RF)": {"features": ["trip_distance"], "model": "rf"},
        "v2_time(RF)": {"features": ["trip_distance", "rush_period"], "model": "rf"},
        "v3_location(RF)": {"features": ["trip_distance", "rush_period", "PULocationID", "DOLocationID"], "model": "rf"},
        "v4_location(GBM)": {"features": ["trip_distance", "rush_period", "PULocationID", "DOLocationID"], "model": "gbm"}
    }
    
    results = {}
    best_score = -float('inf')
    best_model = None
    best_version = ""

    for version, config in scenarios.items():
        features = config["features"]
        model_type = config["model"]
        
        X = df[features].copy()
        y = df[target_col]
        
        # 모델 학습을 위한 Train/Test 분할
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        num_cols = [col for col in features if col == "trip_distance"]
        cat_cols = [col for col in features if col != "trip_distance"]
        
        if model_type == "rf":
            # [v3] Random Forest: OneHotEncoder 사용
            cat_transformer = OneHotEncoder(handle_unknown='ignore')
            regressor = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
            
            transformers = []
            if num_cols:
                transformers.append(('num', StandardScaler(), num_cols))
            if cat_cols:
                transformers.append(('cat', cat_transformer, cat_cols))
            preprocessor = ColumnTransformer(transformers=transformers)
            
        else:
            # [v4] HistGradientBoosting: 범주형 데이터를 정수형/카테고리로 변환 후 직접 투입
            # OrdinalEncoder를 파이프라인 안에서 쓰면 타입이 풀리므로, 데이터 프레임 단계에서 사전 인코딩 수행
            for col in cat_cols:
                X_train[col] = X_train[col].astype('category').cat.codes
                X_test[col] = X_test[col].astype('category').cat.codes
            
            # 수치형만 StandardScaler 태우고, 범주형은 그대로 통과시키기 위한 ColumnTransformer
            transformers = []
            if num_cols:
                transformers.append(('num', StandardScaler(), num_cols))
            # 범주형 컬럼들의 실제 인덱스를 찾아 categorical_features에 정확히 매핑
            cat_indices = [X_train.columns.get_loc(col) for col in cat_cols]
            
            preprocessor = ColumnTransformer(
                transformers=transformers,
                remainder='passthrough' # 범주형 컬럼은 변형 없이 통과
            )
            
            regressor = HistGradientBoostingRegressor(
                categorical_features=cat_indices, random_state=42
            )

        # sklearn Pipeline 구성
        pipeline = Pipeline([
            ('preprocessor', preprocessor),
            ('regressor', regressor)
        ])
        
        print(f"[{version}] 모델 학습 중...")
        pipeline.fit(X_train, y_train)
        
        y_pred = pipeline.predict(X_test)
        r2 = r2_score(y_test, y_pred)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        mae = mean_absolute_error(y_test, y_pred)
        
        results[version] = {"R2": r2, "RMSE": rmse, "MAE": mae}
        print(f"  -> R2: {r2:.4f} | RMSE: {rmse:.4f} | MAE: {mae:.4f}")
        
        if r2 > best_score:
            best_score = r2
            best_model = pipeline
            best_version = version

    model_filename = f"best_model_{target_col}.pkl"
    joblib.dump(best_model, model_filename)
    print(f"\n[결론] 최적 성능 모델: [{best_version}] (R2: {best_score:.4f})")
    print(f"모델 저장 완료: {model_filename}")


def main():
    data_path = Path("data/processed/yellow_taxi_cleaned.parquet")
    
    if not data_path.exists():
        print(f"파일을 찾을 수 없습니다: {data_path}")
        return

    columns_to_load = [
        "trip_duration_min", "trip_distance", "rush_period", 
        "PULocationID", "DOLocationID", 
        "is_long_trip_candidate", "is_large_distance_candidate", "is_large_fare_candidate"
    ]
    df = pd.read_parquet(data_path, columns=columns_to_load)
    
    # 극단값 98건 사전 필터링
    candidate_cols = ["is_long_trip_candidate", "is_large_distance_candidate", "is_large_fare_candidate"]
    candidate_mask = df[candidate_cols].fillna(False).astype(bool).any(axis=1)
    df = df.loc[~candidate_mask].copy()

    df = df.dropna(subset=["PULocationID", "DOLocationID"])
    df["PULocationID"] = df["PULocationID"].astype(str)
    df["DOLocationID"] = df["DOLocationID"].astype(str)

    # 샘플링 수 (안전하게 5만 건으로 유지)
    df = df.sample(n=50000, random_state=42)
    print(f"데이터 정제 완료 (사용 데이터 수: {len(df):,}행)")

    run_advanced_pipeline(df, "trip_duration_min")

if __name__ == "__main__":
    main()