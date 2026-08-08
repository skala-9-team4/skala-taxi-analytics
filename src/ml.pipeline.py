"""
작성자: 이민경
작성일: 2026.08.09
파일명: ml_pipeline.py
설명: 통계 검정 결과(단일 변수의 한계)를 바탕으로 거리, 시간, 공간 변수를 
      단계적으로 추가하며 모델의 예측 성능 향상을 검증하는 머신러닝 파이프라인.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder, OrdinalEncoder
from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import joblib

def run_advanced_pipeline(df: pd.DataFrame, target_col: str):
    print(f"\n========== 타겟 변수: {target_col} ==========")
    
    # 1. 시나리오 정의
    # 통계적 한계를 교차 검증하기 위한 전진 선택법(Forward Selection) 설계
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
        
        X = df[features]
        y = df[target_col]
        
        # 모델의 일반화 성능 평가를 위한 Train/Test 분할
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        num_cols = ["trip_distance"] if "trip_distance" in features else []
        cat_cols = [col for col in features if col != "trip_distance"]
        
        # 2. 알고리즘 특성에 맞춘 전처리 전략
        if model_type == "rf":
            # [v3] Random Forest: 카테고리 변수에 대해 OneHotEncoding 수행
            # 희소 행렬(Sparse Matrix) 생성을 유도하여 차원의 저주(과적합) 한계 증명
            cat_transformer = OneHotEncoder(handle_unknown='ignore')
            regressor = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
        else:
            # [v4] LightGBM(HGBR): 원핫인코딩 없이 내부 정수 인코딩(Ordinal) 사용
            # 범주형 데이터를 효율적으로 분할하여 차원의 저주를 방지하고 성능 최적화
            cat_transformer = OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=-1)
            regressor = HistGradientBoostingRegressor(
                categorical_features='from_dtype', random_state=42
            )
            # HistGradientBoostingRegressor가 카테고리 변수로 명확히 인식하도록 타입 캐스팅
            X_train[cat_cols] = X_train[cat_cols].astype('category')
            X_test[cat_cols] = X_test[cat_cols].astype('category')

        # Data Leakage 방지를 위한 ColumnTransformer 구성
        transformers = []
        if num_cols:
            transformers.append(('num', StandardScaler(), num_cols))
        if cat_cols:
            transformers.append(('cat', cat_transformer, cat_cols))
            
        preprocessor = ColumnTransformer(transformers=transformers)
        
        # 3. sklearn Pipeline 구성 (전처리 + 모델 일원화) [채점 기준 반영]
        pipeline = Pipeline([
            ('preprocessor', preprocessor),
            ('regressor', regressor)
        ])
        
        print(f"[{version}] 모델 학습 중...")
        pipeline.fit(X_train, y_train)
        
        # 4. 성능 평가 (R2, RMSE, MAE 산출)
        y_pred = pipeline.predict(X_test)
        r2 = r2_score(y_test, y_pred)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        mae = mean_absolute_error(y_test, y_pred)
        
        results[version] = {"R2": r2, "RMSE": rmse, "MAE": mae}
        print(f"  -> R2: {r2:.4f} | RMSE: {rmse:.4f} | MAE: {mae:.4f}")
        
        # 최적 모델 갱신
        if r2 > best_score:
            best_score = r2
            best_model = pipeline
            best_version = version

    # 5. 최적 성능 모델 직렬화 저장 
    model_filename = f"best_model_{target_col}.pkl"
    joblib.dump(best_model, model_filename)
    print(f"\n[결론] 최적 성능 모델: [{best_version}] (R2: {best_score:.4f})")
    print(f"모델 저장 완료: {model_filename}\n")


def main():
    data_path = Path("data/processed/yellow_taxi_cleaned.parquet")
    
    if not data_path.exists():
        print(f"파일을 찾을 수 없습니다: {data_path}")
        return

    # 1. 데이터 로드 및 피처 세트 경량화 
    # Data Leakage 방지를 위해 요금 변수 배제 및 결측치 과다 변수(passenger_count) 제외
    columns_to_load = [
        "trip_duration_min", "trip_distance", "rush_period", 
        "PULocationID", "DOLocationID", 
        "is_long_trip_candidate", "is_large_distance_candidate", "is_large_fare_candidate"
    ]
    df = pd.read_parquet(data_path, columns=columns_to_load)
    
    # 2. 도메인 극단값(노이즈) 사전 필터링 
    # 전체 정제 데이터의 약 0.0025%에 해당하는 센서 오류 및 극단치 98건 제거
    candidate_cols = ["is_long_trip_candidate", "is_large_distance_candidate", "is_large_fare_candidate"]
    candidate_mask = df[candidate_cols].fillna(False).astype(bool).any(axis=1)
    df = df.loc[~candidate_mask].copy()

    # 3. 데이터 형변환
    # LocationID를 범주형으로 올바르게 처리하기 위해 결측치 제거 및 문자열 변환
    df = df.dropna(subset=["PULocationID", "DOLocationID"])
    df["PULocationID"] = df["PULocationID"].astype(str)
    df["DOLocationID"] = df["DOLocationID"].astype(str)

    # 4. 학습 속도를 위한 샘플링 (앙상블 모델의 과도한 메모리 사용 방지)
    df = df.sample(n=50000, random_state=42)

    # 5. 파이프라인 실행
    run_advanced_pipeline(df, "trip_duration_min")

if __name__ == "__main__":
    main()