# 데이터 품질 및 전처리 결과

- 원본: `data/raw/yellow_tripdata_2025-01.parquet`
- 크기: 3,475,226행 × 20열
- 검증 항목 및 정제 결과 표본 일치 여부: **일치**
- 정제 결과는 앞·뒤 각 최대 5행과 seed=42 고정 표본을 비교했습니다. 전체 행 해시 검증은 수행하지 않았습니다.

## 로딩 시간·메모리 비교

|              |       Pandas |       Polars |
|:-------------|-------------:|-------------:|
| load_seconds |       1.1727 |       0.7265 |
| rows         | 3475226.0000 | 3475226.0000 |
| columns      |      20.0000 |      20.0000 |
| memory_mb    |     493.4701 |     467.4490 |

시간은 각 라이브러리 1회 측정 참고값입니다. 두 번째 실행은 OS 파일 캐시의 영향을 받을 수 있으며 단일 실행으로 항상 더 빠른 라이브러리를 단정할 수 없습니다. Pandas와 Polars의 메모리 계산 방식도 서로 달라 각 라이브러리 추정치일 뿐 동일 기준의 정밀 벤치마크가 아닙니다.

## 원본 품질 요약

|                     |       Pandas |       Polars |
|:--------------------|-------------:|-------------:|
| rows                |  3.47523e+06 |  3.47523e+06 |
| columns             | 20           | 20           |
| full_duplicate_rows |  0           |  0           |

### 날짜 파싱 실패

|                       |   Pandas |   Polars |
|:----------------------|---------:|---------:|
| tpep_pickup_datetime  |        0 |        0 |
| tpep_dropoff_datetime |        0 |        0 |

CSV 문자열 날짜는 로딩 시 datetime으로 변환하며, 변환 실패 수를 위 표에 별도 집계합니다. 변환된 NaT/null은 이후 핵심 결측 제거 수에도 포함됩니다.

## Pandas EDA 결과

### dtype

|                       | dtype          |
|:----------------------|:---------------|
| VendorID              | int32          |
| tpep_pickup_datetime  | datetime64[us] |
| tpep_dropoff_datetime | datetime64[us] |
| passenger_count       | float64        |
| trip_distance         | float64        |
| RatecodeID            | float64        |
| store_and_fwd_flag    | str            |
| PULocationID          | int32          |
| DOLocationID          | int32          |
| payment_type          | int64          |
| fare_amount           | float64        |
| extra                 | float64        |
| mta_tax               | float64        |
| tip_amount            | float64        |
| tolls_amount          | float64        |
| improvement_surcharge | float64        |
| total_amount          | float64        |
| congestion_surcharge  | float64        |
| Airport_fee           | float64        |
| cbd_congestion_fee    | float64        |

### 결측치

|                       |   missing_count |   missing_ratio_pct |
|:----------------------|----------------:|--------------------:|
| VendorID              |          0.0000 |              0.0000 |
| tpep_pickup_datetime  |          0.0000 |              0.0000 |
| tpep_dropoff_datetime |          0.0000 |              0.0000 |
| passenger_count       |     540149.0000 |             15.5428 |
| trip_distance         |          0.0000 |              0.0000 |
| RatecodeID            |     540149.0000 |             15.5428 |
| store_and_fwd_flag    |     540149.0000 |             15.5428 |
| PULocationID          |          0.0000 |              0.0000 |
| DOLocationID          |          0.0000 |              0.0000 |
| payment_type          |          0.0000 |              0.0000 |
| fare_amount           |          0.0000 |              0.0000 |
| extra                 |          0.0000 |              0.0000 |
| mta_tax               |          0.0000 |              0.0000 |
| tip_amount            |          0.0000 |              0.0000 |
| tolls_amount          |          0.0000 |              0.0000 |
| improvement_surcharge |          0.0000 |              0.0000 |
| total_amount          |          0.0000 |              0.0000 |
| congestion_surcharge  |     540149.0000 |             15.5428 |
| Airport_fee           |     540149.0000 |             15.5428 |
| cbd_congestion_fee    |          0.0000 |              0.0000 |

### 주요 수치형 기초 통계

|                 |        count |    mean |      std |       min |     25% |     50% |     75% |         max |
|:----------------|-------------:|--------:|---------:|----------:|--------:|--------:|--------:|------------:|
| trip_distance   | 3475226.0000 |  5.8551 | 564.6016 |    0.0000 |  0.9800 |  1.6700 |  3.1000 | 276423.5700 |
| fare_amount     | 3475226.0000 | 17.0818 | 463.4729 | -900.0000 |  8.6000 | 12.1100 | 19.5000 | 863372.1200 |
| total_amount    | 3475226.0000 | 25.6113 | 463.6585 | -901.0000 | 15.2000 | 19.9500 | 27.7800 | 863380.3700 |
| extra           | 3475226.0000 |  1.3177 |   1.8615 |   -7.5000 |  0.0000 |  0.0000 |  2.5000 |     15.0000 |
| passenger_count | 2935077.0000 |  1.2979 |   0.7508 |    0.0000 |  1.0000 |  1.0000 |  1.0000 |      9.0000 |

### 날짜 범위

|                       | min                        | max                        |
|:----------------------|:---------------------------|:---------------------------|
| tpep_pickup_datetime  | 2024-12-31T20:47:55.000000 | 2025-02-01T00:00:44.000000 |
| tpep_dropoff_datetime | 2024-12-18T07:52:40.000000 | 2025-02-01T23:44:11.000000 |

### 범주형 컬럼별 고유값 수

|                    |   unique_count |
|:-------------------|---------------:|
| store_and_fwd_flag |         3.0000 |

### 범주형 주요 값 빈도·비율

|                                     |        count |   ratio_pct |
|:------------------------------------|-------------:|------------:|
| ('store_and_fwd_flag', 'N')         | 2927431.0000 |     84.2371 |
| ('store_and_fwd_flag', '<missing>') |  540149.0000 |     15.5428 |
| ('store_and_fwd_flag', 'Y')         |    7646.0000 |      0.2200 |

### 코드 컬럼별 고유값 수

|              |   unique_count |
|:-------------|---------------:|
| VendorID     |         4.0000 |
| RatecodeID   |         8.0000 |
| PULocationID |       261.0000 |
| DOLocationID |       260.0000 |

### 주요 코드 빈도

|                             |        count |
|:----------------------------|-------------:|
| ('VendorID', '2')           | 2719860.0000 |
| ('VendorID', '1')           |  753671.0000 |
| ('VendorID', '7')           |    1206.0000 |
| ('VendorID', '6')           |     489.0000 |
| ('RatecodeID', '1')         | 2756472.0000 |
| ('RatecodeID', '<missing>') |  540149.0000 |
| ('RatecodeID', '2')         |   94420.0000 |
| ('RatecodeID', '99')        |   41963.0000 |
| ('RatecodeID', '5')         |   26501.0000 |
| ('RatecodeID', '3')         |    8622.0000 |
| ('RatecodeID', '4')         |    7092.0000 |
| ('RatecodeID', '6')         |       7.0000 |
| ('PULocationID', '161')     |  169977.0000 |
| ('PULocationID', '237')     |  163703.0000 |
| ('PULocationID', '236')     |  155647.0000 |
| ('PULocationID', '132')     |  146137.0000 |
| ('PULocationID', '230')     |  125829.0000 |
| ('PULocationID', '186')     |  119131.0000 |
| ('PULocationID', '162')     |  117930.0000 |
| ('PULocationID', '142')     |  110585.0000 |
| ('PULocationID', '239')     |   96614.0000 |
| ('PULocationID', '163')     |   95906.0000 |
| ('PULocationID', '234')     |   95896.0000 |
| ('PULocationID', '170')     |   95636.0000 |
| ('PULocationID', '68')      |   91241.0000 |
| ('PULocationID', '138')     |   89658.0000 |
| ('PULocationID', '48')      |   84137.0000 |
| ('PULocationID', '141')     |   81661.0000 |
| ('PULocationID', '79')      |   81576.0000 |
| ('PULocationID', '249')     |   77355.0000 |
| ('PULocationID', '164')     |   76066.0000 |
| ('PULocationID', '140')     |   75093.0000 |
| ('DOLocationID', '236')     |  161376.0000 |
| ('DOLocationID', '237')     |  149970.0000 |
| ('DOLocationID', '161')     |  131258.0000 |
| ('DOLocationID', '230')     |  108177.0000 |
| ('DOLocationID', '170')     |  100060.0000 |
| ('DOLocationID', '142')     |   98982.0000 |
| ('DOLocationID', '239')     |   97559.0000 |
| ('DOLocationID', '162')     |   93798.0000 |
| ('DOLocationID', '141')     |   92675.0000 |
| ('DOLocationID', '68')      |   89232.0000 |
| ('DOLocationID', '234')     |   84669.0000 |
| ('DOLocationID', '163')     |   84631.0000 |
| ('DOLocationID', '48')      |   82722.0000 |
| ('DOLocationID', '238')     |   78467.0000 |
| ('DOLocationID', '186')     |   76338.0000 |
| ('DOLocationID', '79')      |   76009.0000 |
| ('DOLocationID', '140')     |   74165.0000 |
| ('DOLocationID', '263')     |   73889.0000 |
| ('DOLocationID', '164')     |   72594.0000 |
| ('DOLocationID', '229')     |   71480.0000 |

## Polars EDA 결과

### dtype

|                       | dtype                                    |
|:----------------------|:-----------------------------------------|
| VendorID              | Int32                                    |
| tpep_pickup_datetime  | Datetime(time_unit='us', time_zone=None) |
| tpep_dropoff_datetime | Datetime(time_unit='us', time_zone=None) |
| passenger_count       | Int64                                    |
| trip_distance         | Float64                                  |
| RatecodeID            | Int64                                    |
| store_and_fwd_flag    | String                                   |
| PULocationID          | Int32                                    |
| DOLocationID          | Int32                                    |
| payment_type          | Int64                                    |
| fare_amount           | Float64                                  |
| extra                 | Float64                                  |
| mta_tax               | Float64                                  |
| tip_amount            | Float64                                  |
| tolls_amount          | Float64                                  |
| improvement_surcharge | Float64                                  |
| total_amount          | Float64                                  |
| congestion_surcharge  | Float64                                  |
| Airport_fee           | Float64                                  |
| cbd_congestion_fee    | Float64                                  |

### 결측치

|                       |   missing_count |   missing_ratio_pct |
|:----------------------|----------------:|--------------------:|
| VendorID              |          0.0000 |              0.0000 |
| tpep_pickup_datetime  |          0.0000 |              0.0000 |
| tpep_dropoff_datetime |          0.0000 |              0.0000 |
| passenger_count       |     540149.0000 |             15.5428 |
| trip_distance         |          0.0000 |              0.0000 |
| RatecodeID            |     540149.0000 |             15.5428 |
| store_and_fwd_flag    |     540149.0000 |             15.5428 |
| PULocationID          |          0.0000 |              0.0000 |
| DOLocationID          |          0.0000 |              0.0000 |
| payment_type          |          0.0000 |              0.0000 |
| fare_amount           |          0.0000 |              0.0000 |
| extra                 |          0.0000 |              0.0000 |
| mta_tax               |          0.0000 |              0.0000 |
| tip_amount            |          0.0000 |              0.0000 |
| tolls_amount          |          0.0000 |              0.0000 |
| improvement_surcharge |          0.0000 |              0.0000 |
| total_amount          |          0.0000 |              0.0000 |
| congestion_surcharge  |     540149.0000 |             15.5428 |
| Airport_fee           |     540149.0000 |             15.5428 |
| cbd_congestion_fee    |          0.0000 |              0.0000 |

### 주요 수치형 기초 통계

|                 |        count |    mean |      std |       min |     25% |     50% |     75% |         max |
|:----------------|-------------:|--------:|---------:|----------:|--------:|--------:|--------:|------------:|
| trip_distance   | 3475226.0000 |  5.8551 | 564.6016 |    0.0000 |  0.9800 |  1.6700 |  3.1000 | 276423.5700 |
| fare_amount     | 3475226.0000 | 17.0818 | 463.4729 | -900.0000 |  8.6000 | 12.1100 | 19.5000 | 863372.1200 |
| total_amount    | 3475226.0000 | 25.6113 | 463.6585 | -901.0000 | 15.2000 | 19.9500 | 27.7800 | 863380.3700 |
| extra           | 3475226.0000 |  1.3177 |   1.8615 |   -7.5000 |  0.0000 |  0.0000 |  2.5000 |     15.0000 |
| passenger_count | 2935077.0000 |  1.2979 |   0.7508 |    0.0000 |  1.0000 |  1.0000 |  1.0000 |      9.0000 |

### 날짜 범위

|                       | min                        | max                        |
|:----------------------|:---------------------------|:---------------------------|
| tpep_pickup_datetime  | 2024-12-31T20:47:55.000000 | 2025-02-01T00:00:44.000000 |
| tpep_dropoff_datetime | 2024-12-18T07:52:40.000000 | 2025-02-01T23:44:11.000000 |

### 범주형 컬럼별 고유값 수

|                    |   unique_count |
|:-------------------|---------------:|
| store_and_fwd_flag |         3.0000 |

### 범주형 주요 값 빈도·비율

|                                     |        count |   ratio_pct |
|:------------------------------------|-------------:|------------:|
| ('store_and_fwd_flag', 'N')         | 2927431.0000 |     84.2371 |
| ('store_and_fwd_flag', '<missing>') |  540149.0000 |     15.5428 |
| ('store_and_fwd_flag', 'Y')         |    7646.0000 |      0.2200 |

### 코드 컬럼별 고유값 수

|              |   unique_count |
|:-------------|---------------:|
| VendorID     |         4.0000 |
| RatecodeID   |         8.0000 |
| PULocationID |       261.0000 |
| DOLocationID |       260.0000 |

### 주요 코드 빈도

|                             |        count |
|:----------------------------|-------------:|
| ('VendorID', '2')           | 2719860.0000 |
| ('VendorID', '1')           |  753671.0000 |
| ('VendorID', '7')           |    1206.0000 |
| ('VendorID', '6')           |     489.0000 |
| ('RatecodeID', '1')         | 2756472.0000 |
| ('RatecodeID', '<missing>') |  540149.0000 |
| ('RatecodeID', '2')         |   94420.0000 |
| ('RatecodeID', '99')        |   41963.0000 |
| ('RatecodeID', '5')         |   26501.0000 |
| ('RatecodeID', '3')         |    8622.0000 |
| ('RatecodeID', '4')         |    7092.0000 |
| ('RatecodeID', '6')         |       7.0000 |
| ('PULocationID', '161')     |  169977.0000 |
| ('PULocationID', '237')     |  163703.0000 |
| ('PULocationID', '236')     |  155647.0000 |
| ('PULocationID', '132')     |  146137.0000 |
| ('PULocationID', '230')     |  125829.0000 |
| ('PULocationID', '186')     |  119131.0000 |
| ('PULocationID', '162')     |  117930.0000 |
| ('PULocationID', '142')     |  110585.0000 |
| ('PULocationID', '239')     |   96614.0000 |
| ('PULocationID', '163')     |   95906.0000 |
| ('PULocationID', '234')     |   95896.0000 |
| ('PULocationID', '170')     |   95636.0000 |
| ('PULocationID', '68')      |   91241.0000 |
| ('PULocationID', '138')     |   89658.0000 |
| ('PULocationID', '48')      |   84137.0000 |
| ('PULocationID', '141')     |   81661.0000 |
| ('PULocationID', '79')      |   81576.0000 |
| ('PULocationID', '249')     |   77355.0000 |
| ('PULocationID', '164')     |   76066.0000 |
| ('PULocationID', '140')     |   75093.0000 |
| ('DOLocationID', '236')     |  161376.0000 |
| ('DOLocationID', '237')     |  149970.0000 |
| ('DOLocationID', '161')     |  131258.0000 |
| ('DOLocationID', '230')     |  108177.0000 |
| ('DOLocationID', '170')     |  100060.0000 |
| ('DOLocationID', '142')     |   98982.0000 |
| ('DOLocationID', '239')     |   97559.0000 |
| ('DOLocationID', '162')     |   93798.0000 |
| ('DOLocationID', '141')     |   92675.0000 |
| ('DOLocationID', '68')      |   89232.0000 |
| ('DOLocationID', '234')     |   84669.0000 |
| ('DOLocationID', '163')     |   84631.0000 |
| ('DOLocationID', '48')      |   82722.0000 |
| ('DOLocationID', '238')     |   78467.0000 |
| ('DOLocationID', '186')     |   76338.0000 |
| ('DOLocationID', '79')      |   76009.0000 |
| ('DOLocationID', '140')     |   74165.0000 |
| ('DOLocationID', '263')     |   73889.0000 |
| ('DOLocationID', '164')     |   72594.0000 |
| ('DOLocationID', '229')     |   71480.0000 |

## Pandas와 Polars의 원본 EDA 결과 비교

|           | 일치   |
|:----------|:-----|
| 원본 행·열 수  | 통과   |
| 컬럼별 결측치   | 통과   |
| 날짜 범위     | 통과   |
| 범주·코드 고유값 | 통과   |
| 범주형 전체 빈도 | 통과   |
| 코드 전체 빈도  | 통과   |
| 주요 수치 통계  | 통과   |
| 완전 중복 행   | 통과   |

dtype 이름은 라이브러리 고유 표현이므로 값 일치 판정에서 제외했습니다. 수치에는 rtol/atol 1e-9를 적용하고 null/NaN과 정수/실수 표현을 정규화했습니다.

## 분석 기간 점검

- 파일명 기준 연월: `2025-01`
- 실제 연월 수: 3
- 여러 연월 혼재: True
- 정제 후 기준 연월 밖 행: 22

| tpep_pickup_datetime   |        rows |
|:-----------------------|------------:|
| 2024-12                | 21          |
| 2025-01                |  3.4752e+06 |
| 2025-02                |  1          |

분석 대상을 2025-01로 한정하면 `is_outside_source_month == False`인 행을 주 분석에 사용합니다. 정제 후 확인된 기준 연월 밖 22행은 데이터 준비 단계에서 삭제하지 않았으며, 포함 여부는 후속 분석 목적에 따라 결정하고 필요하면 포함·제외 결과를 비교합니다.

## Pandas와 Polars의 단계별 정제 결과 비교

|                                               |           Pandas |           Polars |
|:----------------------------------------------|-----------------:|-----------------:|
| raw_rows                                      |      3.47523e+06 |      3.47523e+06 |
| duplicate_rows_removed                        |      0           |      0           |
| core_missing_rows_removed                     |      0           |      0           |
| invalid_datetime_rows_removed                 |      0           |      0           |
| nonpositive_duration_rows                     |   2051           |   2051           |
| nonpositive_distance_rows                     |  90893           |  90893           |
| nonpositive_fare_rows                         | 145516           | 145516           |
| nonpositive_duration_distance_or_fare_removed | 222712           | 222712           |
| cleaned_rows                                  |      3.25251e+06 |      3.25251e+06 |

## 요금 지표의 의미

- `fare_amount`는 택시미터가 시간과 이동거리를 기준으로 계산한 운임이며, 본 분석의 주요 요금 지표로 사용합니다.
- `total_amount`는 승객에게 청구된 총금액이며, 현금으로 지급된 팁은 포함되지 않습니다.
- 아래 출퇴근 집단 비교의 `fare_amount` 통계는 미터 운임 통계입니다.

## 생성된 파생 변수

|                          | 정의                                                    |
|:-------------------------|:------------------------------------------------------|
| trip_duration_min        | 하차 시각 - 승차 시각(분)                                      |
| pickup_hour              | 승차 시각의 시(0~23)                                        |
| day_of_week              | 승차 요일명                                                |
| is_weekday               | 월요일~금요일 여부                                            |
| is_rush_hour             | 평일 06:00 이상 10:00 미만 또는 16:00 이상 20:00 미만 여부          |
| rush_period              | morning_rush/evening_rush/weekday_non_rush/weekend 분류 |
| weekday_comparison_group | weekday_rush 또는 weekday_non_rush; 주말은 결측              |
| fare_per_mile            | fare_amount / trip_distance                           |
| average_speed_mph        | trip_distance / (trip_duration_min / 60)              |

## 출퇴근 시간대 분류

| rush_period      |        count |   ratio_pct |
|:-----------------|-------------:|------------:|
| morning_rush     |  359592.0000 |     11.0558 |
| evening_rush     |  662764.0000 |     20.3770 |
| weekday_non_rush | 1399820.0000 |     43.0381 |
| weekend          |  830338.0000 |     25.5291 |

주 비교 집단은 `weekday_rush`와 `weekday_non_rush`이며 주말은 비교 집단에서 제외합니다.

## 평일 출퇴근·비출퇴근 핵심 변수 기초 통계

|                                           |        count |    mean |       std |    min |    25% |     50% |     75% |          max |
|:------------------------------------------|-------------:|--------:|----------:|-------:|-------:|--------:|--------:|-------------:|
| ('weekday_rush', 'trip_duration_min')     | 1022356.0000 | 15.4745 |   27.1540 | 0.0167 | 7.3500 | 11.6833 | 18.3833 |    2875.1667 |
| ('weekday_rush', 'fare_amount')           | 1022356.0000 | 17.5457 |   15.9801 | 0.0100 | 8.6000 | 12.8000 | 19.1000 |     936.8000 |
| ('weekday_rush', 'trip_distance')         | 1022356.0000 |  6.1287 |  565.6933 | 0.0100 | 0.9800 |  1.6000 |  2.8700 |  222167.4900 |
| ('weekday_rush', 'fare_per_mile')         | 1022356.0000 | 23.6728 |  200.3106 | 0.0000 | 6.0370 |  7.4691 |  9.3000 |   25000.0000 |
| ('weekday_rush', 'average_speed_mph')     | 1022356.0000 | 22.5008 | 2499.8467 | 0.0006 | 7.1102 |  9.0836 | 11.9873 | 1437122.7000 |
| ('weekday_non_rush', 'trip_duration_min') | 1399820.0000 | 15.4749 |   27.9922 | 0.0167 | 7.5167 | 12.0000 | 18.8333 |    5626.3167 |
| ('weekday_non_rush', 'fare_amount')       | 1399820.0000 | 19.0118 |  729.9105 | 0.0100 | 8.6000 | 12.8000 | 20.5000 |  863372.1200 |
| ('weekday_non_rush', 'trip_distance')     | 1399820.0000 |  5.0836 |  450.5494 | 0.0100 | 1.0200 |  1.7200 |  3.2900 |  206137.9900 |
| ('weekday_non_rush', 'fare_per_mile')     | 1399820.0000 | 12.0944 |  479.3028 | 0.0000 | 5.6250 |  7.1910 |  9.1429 |  539607.5750 |
| ('weekday_non_rush', 'average_speed_mph') | 1399820.0000 | 24.7504 | 4469.2716 | 0.0004 | 7.2258 |  9.5522 | 13.1849 | 3722496.9000 |

이 표는 후속 시각화와 통계 검정을 위한 데이터 품질 확인이며 평균 차이만으로 결론을 내리지 않습니다.

## 보존된 이상치 후보

|                                |   rows |
|:-------------------------------|-------:|
| is_long_trip_candidate         |     13 |
| is_large_distance_candidate    |    101 |
| is_large_fare_candidate        |      3 |
| is_invalid_passenger_candidate |  23635 |

이상치 후보 플래그는 데이터 오류를 확정한 값이 아니며, 이번 전처리 단계에서는 후보 행을 임의로 제거하지 않았습니다.

## 정제 및 EDA 실행 시간 비교

|               |    Pandas |   Polars |
|:--------------|----------:|---------:|
| eda_seconds   | 26.670375 | 9.167049 |
| clean_seconds | 32.591019 | 5.491783 |

## 검증 항목 및 정제 결과 표본 일치 여부

|                | 일치   |
|:---------------|:-----|
| 원본 행·열 수       | 통과   |
| 컬럼별 결측치        | 통과   |
| 날짜 범위          | 통과   |
| 범주·코드 고유값      | 통과   |
| 범주형 전체 빈도      | 통과   |
| 코드 전체 빈도       | 통과   |
| 주요 수치 통계       | 통과   |
| 출퇴근 분류 분포      | 통과   |
| 평일 출퇴근·비출퇴근 통계 | 통과   |
| 완전 중복 행        | 통과   |
| 단계별 제거 행 수     | 통과   |
| 이상치 후보 집계      | 통과   |
| 분석 기간 플래그 집계   | 통과   |
| 최종 컬럼 순서       | 통과   |
| 정제 결과 표본·파생 변수 | 통과   |

- 결론: **검증 항목과 정제 결과 표본이 일치합니다.**
### 차이 항목과 실제 비교 실패 이유

- 없음

## 후속 분석 시 해석 주의사항

- 후속 시각화와 통계 검정에서는 이상치 후보를 포함한 결과와 제외한 결과를 함께 확인하여, 소수의 극단값이 이동시간과 미터 운임의 평균 차이 및 검정 결과에 미치는 영향을 점검해야 합니다. 두 분석의 결론이 달라질 경우 이상치 처리 기준과 결과의 민감성을 함께 보고해야 합니다.
- 이상치 후보의 포함·제외 분석은 후속 시각화와 통계 분석 단계에서 수행하며, 이 보고서에는 데이터에서 확인하지 않은 수치나 분석 결론을 작성하지 않습니다.
- 이동시간과 미터 운임은 이동거리, 승·하차 지역, 요금 코드 및 기타 요금 구성의 영향을 받을 수 있습니다.
- 현재 출퇴근 시간대 분류는 요일만을 기준으로 하며, 평일 공휴일을 별도로 제외하지 않았습니다. 따라서 공휴일의 이동 특성이 평일 출퇴근 집단에 일부 포함될 수 있습니다.
- 평일 비출퇴근 집단에는 새벽·주간·야간이 모두 포함되므로, 후속 회귀 또는 ML 분석에서는 승차 시각, 승하차 지역, 이동거리 등의 변수를 함께 고려해야 합니다.
- 기존 이상치 후보를 제외해도 모든 파생 변수 극단값이 제거되는 것은 아닙니다. `fare_per_mile`과 `average_speed_mph`의 분포는 평균뿐 아니라 중앙값과 사분위수를 함께 확인해야 합니다.
- 현실적으로 해석하기 어려운 속도와 단위 거리당 미터 운임은 포함·제외 결과를 비교하고, 이동거리 차이를 고려하지 않은 채 출퇴근 집단의 이동시간이나 미터 운임 차이를 해석하지 않습니다.
- 시각화와 t-test는 집단 간 차이를 확인하는 단계이며, 이 준비 단계에서는 수행하지 않습니다.
- 관측 데이터이므로 결과는 엄밀한 인과관계가 아니라 차이 또는 연관성으로 해석해야 합니다.