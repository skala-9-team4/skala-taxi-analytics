# skala-taxi-analytics

NYC Yellow Taxi의 출퇴근 시간대별 이동시간과 요금을 분석하는 프로젝트입니다.

## 환경 설정 (macOS/Linux)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Jupyter 커널이 필요하다면 `jupyter`와 `ipykernel`을 별도로 설치한 뒤 등록합니다. 현재 코드가 두 패키지를 사용하지 않아 공통 의존성에는 넣지 않았습니다.

```bash
pip install jupyter ipykernel
python -m ipykernel install --user \
  --name skala-taxi-analysis \
  --display-name "Python (skala-taxi-analysis)"
```

## 원본 데이터와 실행

NYC TLC Yellow Taxi CSV 또는 Parquet 파일을 `data/raw/`에 둡니다. 원본과 생성 결과는 Git에서 제외되며 원본은 수정하지 않습니다.

```bash
mkdir -p data/raw data/processed
curl -fL https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2026-05.parquet \
  -o data/raw/yellow_tripdata_2026-05.parquet
.venv/bin/python src/run_all.py
.venv/bin/python src/run_all.py --input data/raw/yellow_tripdata_YYYY-MM.parquet
.venv/bin/python src/run_all.py --input data/raw/yellow_tripdata_YYYY-MM.csv
```

가상환경을 활성화한 상태에서는 다음과 같이 실행합니다.

```bash
python src/run_all.py
```

가상환경을 활성화하지 않았다면 프로젝트 가상환경의 Python을 직접 지정하여 실행할 수 있습니다.

```bash
.venv/bin/python src/run_all.py
```

인수 없이 실행하면 다음 파일을 기본 입력으로 사용합니다.

```bash
data/raw/yellow_tripdata_2026-05.parquet
```

다른 파일을 분석하려면 `--input`으로 해당 파일 경로를 지정합니다. 위 URL은 이 저장소의 분석에 사용한 2026년 5월 데이터입니다. 분석 대상 월이 정해지면 파일명과 URL의 월을 함께 변경합니다. 로딩 시간과 정제·EDA 시간은 한 프로세스에서 각 라이브러리를 한 번씩 측정한 참고값이며 OS 파일 캐시와 실행 환경에 따라 달라질 수 있습니다. 단일 실행 시간만으로 특정 라이브러리가 항상 더 빠르다고 단정하지 않습니다.

기본 결과는 다음 위치에 생성됩니다.

- `data/processed/yellow_taxi_cleaned.parquet`: 원본 컬럼을 유지한 정제 데이터
- `reports/generated/data_quality_report.md`: 로딩 비교, EDA, 처리 전후 품질 요약

다른 경로가 필요하면 `--output`과 `--report`를 사용합니다.

## 정제 기준

- 전체 컬럼이 완전히 같은 행만 중복으로 제거합니다.
- 승·하차 시각, 이동 거리, 미터 운임의 결측 행만 제거합니다.
- 파싱할 수 없는 시각과 운행시간·거리·미터 운임이 0 이하인 행은 주제 분석에 유효하지 않아 제거합니다.
- CSV와 Parquet 모두 승·하차 시각을 `datetime`으로 정규화하며, 변환 실패 값은 `NaT`로 바꿔 핵심 결측 기준으로 제거합니다.
- 장시간(1,440분 초과), 200마일 초과, 미터 운임 1,000달러 초과 및 승객 수 0 이하/8명 초과는 절대적인 오류 판정이 아닌 보수적인 임시 기준입니다. 해당 행은 삭제하지 않고 검토용 플래그로 보존합니다.
- 파일명에 `YYYY-MM`이 있으면 실제 승차 연월과 비교해 범위 밖 행을 표시합니다. 연월을 추출할 수 없으면 임의의 기간을 적용하지 않으며 실제 연월별 분포와 여러 연월 혼재 여부만 보고합니다.
- 평일 오전 06:00 이상 10:00 미만과 오후 16:00 이상 20:00 미만을 출퇴근 시간대로 정의합니다. 주말은 출퇴근 시간대에 포함하지 않습니다.
- `trip_duration_min`, `pickup_hour`, `day_of_week`, `is_weekday`, `is_rush_hour`, `rush_period`, `weekday_comparison_group`, `fare_per_mile`, `average_speed_mph`를 생성합니다.
- `rush_period`는 `morning_rush`, `evening_rush`, `weekday_non_rush`, `weekend`로 구분합니다. 주 비교에는 `weekday_rush`와 `weekday_non_rush`만 사용하여 주말 효과가 섞이지 않게 합니다.
- `fare_per_mile`과 `average_speed_mph`는 거리·시간이 0보다 큰 행에서만 계산하며 극단값을 이유로 행을 임의 삭제하지 않습니다.

Pandas와 Polars는 동일 원본에서 순차적으로 독립 로딩하여 각각 결측치·완전 중복·유효하지 않은 운행을 처리하고 동일 파생 변수를 생성합니다. 각 라이브러리의 기본 EDA와 단계별 제거 행 수, 정제 후 표본 및 파생 변수는 dtype 이름, null/NaN 표현과 미세 부동소수점 차이를 정규화한 뒤 비교합니다. EDA 집계는 인덱스와 컬럼명을 포함해 비교하며, 코드 빈도는 전체 값을 비교하고 보고서 표시만 상위 20개로 제한합니다. 기존 최종 Parquet은 Pandas 결과로 한 번만 저장합니다.

생성 보고서는 Pandas EDA, Polars EDA, 원본 EDA 비교, 단계별 정제 비교, 정제·EDA 실행 시간 및 전체 검증 항목과 정제 표본 일치 여부를 구분하여 기록합니다. 실제 값 차이가 있으면 차이 항목을 숨기지 않고 결론에 표시합니다.

Pandas와 Polars의 구조·결측치뿐 아니라 앞·뒤 각 최대 5행과 seed 42로 뽑은 고정 표본의 주요 분석 컬럼 값도 정규화하여 비교합니다. 대용량 정제 결과 전체를 서로 변환하거나 동시에 보관하지 않기 위해 전체 행 해시는 계산하지 않으며, 보고서 결론은 “검증 항목 및 정제 결과 표본 일치 여부”로 제한합니다.

## 후속 분석 시 주의사항

- `fare_amount`는 택시미터가 시간과 이동거리를 기준으로 계산한 운임이며, 본 분석의 주요 요금 지표로 사용합니다. `total_amount`는 승객에게 청구된 총금액이며, 현금으로 지급된 팁은 포함되지 않습니다.
- 이동시간과 미터 운임은 이동거리, 승·하차 지역, 요금 코드, 공항 요금·통행료·팁 등 여러 변수의 영향을 받을 수 있습니다.
- 시각화와 t-test는 집단 간 차이를 확인하는 후속 단계이며, 이 데이터 준비 단계에서는 구현하지 않습니다.
- 관측 데이터이므로 결과를 엄밀한 인과관계로 단정하지 않고 차이 또는 연관성으로 해석해야 합니다.
- 이상치 후보 플래그는 데이터 오류를 확정한 값이 아니며, 이번 전처리 단계에서는 후보 행을 임의로 제거하지 않습니다.
- 후속 시각화와 통계 검정에서는 이상치 후보를 포함한 결과와 제외한 결과를 함께 확인하여, 소수의 극단값이 이동시간과 미터 운임의 평균 차이 및 검정 결과에 미치는 영향을 점검해야 합니다. 두 분석의 결론이 달라질 경우 이상치 처리 기준과 결과의 민감성을 함께 보고해야 합니다.
- 이상치 후보의 포함·제외 분석은 후속 시각화와 통계 분석 단계에서 수행하며, 이 단계에서는 데이터에서 확인하지 않은 수치나 분석 결론을 작성하지 않습니다.
- 파일명에서 기준 연월을 추출한 경우에도 범위 밖 행은 준비 단계에서 삭제하지 않습니다. 2026년 5월을 주 분석 대상으로 한정할 때는 `is_outside_source_month == False`인 행을 사용하며, 범위 밖 행의 포함 여부는 후속 분석 목적에 따라 결정하고 필요하면 포함·제외 결과를 비교합니다.
- 현재 출퇴근 시간대 분류는 요일만을 기준으로 하며, 평일 공휴일을 별도로 제외하지 않았습니다. 따라서 공휴일의 이동 특성이 평일 출퇴근 집단에 일부 포함될 수 있습니다.
- 평일 비출퇴근 집단에는 새벽·주간·야간이 모두 포함되므로, 후속 회귀 또는 ML 분석에서는 승차 시각, 승하차 지역, 이동거리 등의 변수를 함께 고려해야 합니다.
- 기존 이상치 후보를 제외해도 모든 파생 변수 극단값이 제거되는 것은 아닙니다. `fare_per_mile`과 `average_speed_mph`의 분포는 평균뿐 아니라 중앙값과 사분위수를 함께 확인하고, 현실적으로 해석하기 어려운 값은 포함·제외 결과를 비교해야 합니다.
- 출퇴근 집단의 이동시간과 미터 운임 차이는 이동거리 차이를 함께 고려하여 해석해야 합니다.

## 테스트

```bash
python -m pytest -q
```
