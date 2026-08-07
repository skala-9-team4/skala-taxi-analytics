# skala-taxi-analytics

NYC Yellow Taxi의 출퇴근 시간대별 이동시간과 요금을 분석하는 프로젝트입니다. 현재 구현 범위는 원본 로딩, Pandas/Polars 비교, 기본 EDA와 데이터 정제까지입니다.

## 환경 설정 (macOS/Linux)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Jupyter 커널이 필요한 팀원은 `jupyter`와 `ipykernel`을 별도로 설치한 뒤 등록합니다. 현재 코드가 두 패키지를 사용하지 않아 공통 의존성에는 넣지 않았습니다.

```bash
pip install jupyter ipykernel
python -m ipykernel install --user \
  --name skala-taxi-analysis \
  --display-name "Python (skala-taxi-analysis)"
```

## 원본 데이터와 실행

NYC TLC Yellow Taxi CSV 또는 Parquet 파일을 `data/raw/`에 둡니다. 원본과 생성 결과는 Git에서 제외되며 원본은 수정하지 않습니다.

```bash
curl -fL https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2025-01.parquet \
  -o data/raw/yellow_tripdata_2025-01.parquet
.venv/bin/python src/prepare_data.py
.venv/bin/python src/prepare_data.py data/raw/yellow_tripdata_YYYY-MM.parquet
.venv/bin/python src/prepare_data.py data/raw/yellow_tripdata_YYYY-MM.csv
```

가상환경을 활성화한 상태에서는 다음과 같이 실행합니다.

```bash
python src/prepare_data.py
```

가상환경을 활성화하지 않았다면 프로젝트 가상환경의 Python을 직접 지정하여 실행할 수 있습니다.

```bash
.venv/bin/python src/prepare_data.py
```

인수 없이 실행하면 다음 파일을 기본 입력으로 사용합니다.

```bash
data/raw/yellow_tripdata_2025-01.parquet
```

다른 파일을 분석하려면 첫 번째 인수로 해당 파일 경로를 지정합니다. 위 URL은 이 저장소의 검증에 사용한 2025년 1월 예시입니다. 분석 대상 월이 정해지면 파일명과 URL의 월을 함께 변경합니다. 로딩 시간은 한 프로세스에서 각 라이브러리를 한 번씩 측정한 참고값이며 OS 파일 캐시에 따라 달라질 수 있습니다.

기본 결과는 다음 위치에 생성됩니다.

- `data/processed/yellow_taxi_cleaned.parquet`: 원본 컬럼을 유지한 정제 데이터
- `reports/generated/data_quality_report.md`: 로딩 비교, EDA, 처리 전후 품질 요약

다른 경로가 필요하면 `--output`과 `--report`를 사용합니다.

## 정제 기준

- 전체 컬럼이 완전히 같은 행만 중복으로 제거합니다.
- 승·하차 시각, 이동 거리, 기본요금의 결측 행만 제거합니다.
- 파싱할 수 없는 시각과 운행시간·거리·기본요금이 0 이하인 행은 주제 분석에 유효하지 않아 제거합니다.
- CSV와 Parquet 모두 승·하차 시각을 `datetime`으로 정규화하며, 변환 실패 값은 `NaT`로 바꿔 핵심 결측 기준으로 제거합니다.
- 장시간(1,440분 초과), 200마일 초과, 기본요금 1,000달러 초과 및 승객 수 0 이하/8명 초과는 절대적인 오류 판정이 아닌 보수적인 임시 기준입니다. 해당 행은 삭제하지 않고 검토용 플래그로 보존합니다.
- 파일명에 `YYYY-MM`이 있으면 실제 승차 연월과 비교해 범위 밖 행을 표시합니다. 연월을 추출할 수 없으면 임의의 기간을 적용하지 않으며 실제 연월별 분포와 여러 연월 혼재 여부만 보고합니다.
- `trip_duration_min`, `pickup_hour`, `day_of_week`, `is_weekday`만 생성합니다. `is_rush_hour`는 팀의 시간대 정의가 확정된 뒤 추가합니다.

정제 전후 행 수, 결측·중복·오류 후보와 주요 통계는 생성 보고서에서 확인할 수 있습니다.

Pandas와 Polars의 구조·결측치뿐 아니라 앞·뒤 각 최대 5행과 seed 42로 뽑은 고정 표본의 주요 분석 컬럼 값도 정규화하여 비교합니다.

## 테스트

```bash
python -m pytest -q
```
