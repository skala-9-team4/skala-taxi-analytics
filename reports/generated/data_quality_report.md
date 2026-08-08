# 데이터 품질 및 전처리 결과

- 원본: `data\raw\yellow_tripdata_2026-05.parquet`
- 크기: 4,090,836행 × 20열
- 검증 항목 및 정제 결과 표본 일치 여부: **일치**
- 정제 결과는 앞·뒤 각 최대 5행과 seed=42 고정 표본을 비교했습니다. 전체 행 해시 검증은 수행하지 않았습니다.

## 로딩 시간·메모리 비교

|              |       Pandas |       Polars |
|:-------------|-------------:|-------------:|
| load_seconds |       0.1903 |       0.1407 |
| rows         | 4090836.0000 | 4090836.0000 |
| columns      |      20.0000 |      20.0000 |
| memory_mb    |     580.6241 |     550.1264 |

시간은 각 라이브러리 1회 측정 참고값입니다. 두 번째 실행은 OS 파일 캐시의 영향을 받을 수 있으며 단일 실행으로 항상 더 빠른 라이브러리를 단정할 수 없습니다. Pandas와 Polars의 메모리 계산 방식도 서로 달라 각 라이브러리 추정치일 뿐 동일 기준의 정밀 벤치마크가 아닙니다.

## 원본 품질 요약

|                     |       Pandas |       Polars |
|:--------------------|-------------:|-------------:|
| rows                |  4.09084e+06 |  4.09084e+06 |
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
| passenger_count       |     955371.0000 |             23.3539 |
| trip_distance         |          0.0000 |              0.0000 |
| RatecodeID            |     955371.0000 |             23.3539 |
| store_and_fwd_flag    |     955371.0000 |             23.3539 |
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
| congestion_surcharge  |     955371.0000 |             23.3539 |
| Airport_fee           |     955371.0000 |             23.3539 |
| cbd_congestion_fee    |          0.0000 |              0.0000 |

### 주요 수치형 기초 통계

|                 |        count |    mean |      std |       min |     25% |     50% |     75% |         max |
|:----------------|-------------:|--------:|---------:|----------:|--------:|--------:|--------:|------------:|
| trip_distance   | 4090836.0000 |  4.9548 | 483.6157 |    0.0000 |  1.0400 |  1.8700 |  3.8100 | 307491.4700 |
| fare_amount     | 4090836.0000 | 21.5132 |  19.0130 | -950.0000 | 10.0000 | 16.3000 | 26.8000 |   5525.9900 |
| total_amount    | 4090836.0000 | 30.4851 |  22.9750 | -951.0000 | 17.6400 | 23.9400 | 34.9500 |   5530.7400 |
| extra           | 4090836.0000 |  1.1232 |   1.7506 |   -7.5000 |  0.0000 |  0.0000 |  2.5000 |     15.2500 |
| passenger_count | 3135465.0000 |  1.2433 |   0.6367 |    0.0000 |  1.0000 |  1.0000 |  1.0000 |      9.0000 |

### 날짜 범위

|                       | min                        | max                        |
|:----------------------|:---------------------------|:---------------------------|
| tpep_pickup_datetime  | 2008-12-31T23:05:53.000000 | 2026-06-01T00:20:35.000000 |
| tpep_dropoff_datetime | 2009-01-01T17:08:07.000000 | 2026-06-02T12:53:42.000000 |

### 범주형 컬럼별 고유값 수

|                    |   unique_count |
|:-------------------|---------------:|
| store_and_fwd_flag |         3.0000 |

### 범주형 주요 값 빈도·비율

|                                     |        count |   ratio_pct |
|:------------------------------------|-------------:|------------:|
| ('store_and_fwd_flag', 'N')         | 3131868.0000 |     76.5581 |
| ('store_and_fwd_flag', '<missing>') |  955371.0000 |     23.3539 |
| ('store_and_fwd_flag', 'Y')         |    3597.0000 |      0.0879 |

### 코드 컬럼별 고유값 수

|              |   unique_count |
|:-------------|---------------:|
| VendorID     |         4.0000 |
| RatecodeID   |         8.0000 |
| PULocationID |       259.0000 |
| DOLocationID |       260.0000 |

### 주요 코드 빈도

|                             |        count |
|:----------------------------|-------------:|
| ('VendorID', '2')           | 3226222.0000 |
| ('VendorID', '1')           |  805221.0000 |
| ('VendorID', '7')           |   51750.0000 |
| ('VendorID', '6')           |    7643.0000 |
| ('RatecodeID', '1')         | 2842930.0000 |
| ('RatecodeID', '<missing>') |  955371.0000 |
| ('RatecodeID', '99')        |  140897.0000 |
| ('RatecodeID', '2')         |   95155.0000 |
| ('RatecodeID', '5')         |   35523.0000 |
| ('RatecodeID', '3')         |   12567.0000 |
| ('RatecodeID', '4')         |    8392.0000 |
| ('RatecodeID', '6')         |       1.0000 |
| ('PULocationID', '237')     |  198008.0000 |
| ('PULocationID', '236')     |  175969.0000 |
| ('PULocationID', '161')     |  161315.0000 |
| ('PULocationID', '132')     |  149312.0000 |
| ('PULocationID', '142')     |  124523.0000 |
| ('PULocationID', '162')     |  120488.0000 |
| ('PULocationID', '186')     |  113921.0000 |
| ('PULocationID', '230')     |  111934.0000 |
| ('PULocationID', '239')     |  108689.0000 |
| ('PULocationID', '79')      |  107374.0000 |
| ('PULocationID', '138')     |  106388.0000 |
| ('PULocationID', '170')     |  102755.0000 |
| ('PULocationID', '234')     |  101697.0000 |
| ('PULocationID', '163')     |  100524.0000 |
| ('PULocationID', '68')      |   99835.0000 |
| ('PULocationID', '141')     |   91725.0000 |
| ('PULocationID', '249')     |   89571.0000 |
| ('PULocationID', '48')      |   89093.0000 |
| ('PULocationID', '238')     |   80807.0000 |
| ('PULocationID', '140')     |   78479.0000 |
| ('DOLocationID', '236')     |  179446.0000 |
| ('DOLocationID', '237')     |  177568.0000 |
| ('DOLocationID', '161')     |  138367.0000 |
| ('DOLocationID', '142')     |  110032.0000 |
| ('DOLocationID', '170')     |  109177.0000 |
| ('DOLocationID', '230')     |  109064.0000 |
| ('DOLocationID', '239')     |  107804.0000 |
| ('DOLocationID', '162')     |  104656.0000 |
| ('DOLocationID', '141')     |  100319.0000 |
| ('DOLocationID', '68')      |   97921.0000 |
| ('DOLocationID', '234')     |   91489.0000 |
| ('DOLocationID', '163')     |   91274.0000 |
| ('DOLocationID', '79')      |   90723.0000 |
| ('DOLocationID', '238')     |   88091.0000 |
| ('DOLocationID', '48')      |   87034.0000 |
| ('DOLocationID', '246')     |   82612.0000 |
| ('DOLocationID', '263')     |   82001.0000 |
| ('DOLocationID', '140')     |   79371.0000 |
| ('DOLocationID', '229')     |   78312.0000 |
| ('DOLocationID', '186')     |   76263.0000 |

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
| passenger_count       |     955371.0000 |             23.3539 |
| trip_distance         |          0.0000 |              0.0000 |
| RatecodeID            |     955371.0000 |             23.3539 |
| store_and_fwd_flag    |     955371.0000 |             23.3539 |
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
| congestion_surcharge  |     955371.0000 |             23.3539 |
| Airport_fee           |     955371.0000 |             23.3539 |
| cbd_congestion_fee    |          0.0000 |              0.0000 |

### 주요 수치형 기초 통계

|                 |        count |    mean |      std |       min |     25% |     50% |     75% |         max |
|:----------------|-------------:|--------:|---------:|----------:|--------:|--------:|--------:|------------:|
| trip_distance   | 4090836.0000 |  4.9548 | 483.6157 |    0.0000 |  1.0400 |  1.8700 |  3.8100 | 307491.4700 |
| fare_amount     | 4090836.0000 | 21.5132 |  19.0130 | -950.0000 | 10.0000 | 16.3000 | 26.8000 |   5525.9900 |
| total_amount    | 4090836.0000 | 30.4851 |  22.9750 | -951.0000 | 17.6400 | 23.9400 | 34.9500 |   5530.7400 |
| extra           | 4090836.0000 |  1.1232 |   1.7506 |   -7.5000 |  0.0000 |  0.0000 |  2.5000 |     15.2500 |
| passenger_count | 3135465.0000 |  1.2433 |   0.6367 |    0.0000 |  1.0000 |  1.0000 |  1.0000 |      9.0000 |

### 날짜 범위

|                       | min                        | max                        |
|:----------------------|:---------------------------|:---------------------------|
| tpep_pickup_datetime  | 2008-12-31T23:05:53.000000 | 2026-06-01T00:20:35.000000 |
| tpep_dropoff_datetime | 2009-01-01T17:08:07.000000 | 2026-06-02T12:53:42.000000 |

### 범주형 컬럼별 고유값 수

|                    |   unique_count |
|:-------------------|---------------:|
| store_and_fwd_flag |         3.0000 |

### 범주형 주요 값 빈도·비율

|                                     |        count |   ratio_pct |
|:------------------------------------|-------------:|------------:|
| ('store_and_fwd_flag', 'N')         | 3131868.0000 |     76.5581 |
| ('store_and_fwd_flag', '<missing>') |  955371.0000 |     23.3539 |
| ('store_and_fwd_flag', 'Y')         |    3597.0000 |      0.0879 |

### 코드 컬럼별 고유값 수

|              |   unique_count |
|:-------------|---------------:|
| VendorID     |         4.0000 |
| RatecodeID   |         8.0000 |
| PULocationID |       259.0000 |
| DOLocationID |       260.0000 |

### 주요 코드 빈도

|                             |        count |
|:----------------------------|-------------:|
| ('VendorID', '2')           | 3226222.0000 |
| ('VendorID', '1')           |  805221.0000 |
| ('VendorID', '7')           |   51750.0000 |
| ('VendorID', '6')           |    7643.0000 |
| ('RatecodeID', '1')         | 2842930.0000 |
| ('RatecodeID', '<missing>') |  955371.0000 |
| ('RatecodeID', '99')        |  140897.0000 |
| ('RatecodeID', '2')         |   95155.0000 |
| ('RatecodeID', '5')         |   35523.0000 |
| ('RatecodeID', '3')         |   12567.0000 |
| ('RatecodeID', '4')         |    8392.0000 |
| ('RatecodeID', '6')         |       1.0000 |
| ('PULocationID', '237')     |  198008.0000 |
| ('PULocationID', '236')     |  175969.0000 |
| ('PULocationID', '161')     |  161315.0000 |
| ('PULocationID', '132')     |  149312.0000 |
| ('PULocationID', '142')     |  124523.0000 |
| ('PULocationID', '162')     |  120488.0000 |
| ('PULocationID', '186')     |  113921.0000 |
| ('PULocationID', '230')     |  111934.0000 |
| ('PULocationID', '239')     |  108689.0000 |
| ('PULocationID', '79')      |  107374.0000 |
| ('PULocationID', '138')     |  106388.0000 |
| ('PULocationID', '170')     |  102755.0000 |
| ('PULocationID', '234')     |  101697.0000 |
| ('PULocationID', '163')     |  100524.0000 |
| ('PULocationID', '68')      |   99835.0000 |
| ('PULocationID', '141')     |   91725.0000 |
| ('PULocationID', '249')     |   89571.0000 |
| ('PULocationID', '48')      |   89093.0000 |
| ('PULocationID', '238')     |   80807.0000 |
| ('PULocationID', '140')     |   78479.0000 |
| ('DOLocationID', '236')     |  179446.0000 |
| ('DOLocationID', '237')     |  177568.0000 |
| ('DOLocationID', '161')     |  138367.0000 |
| ('DOLocationID', '142')     |  110032.0000 |
| ('DOLocationID', '170')     |  109177.0000 |
| ('DOLocationID', '230')     |  109064.0000 |
| ('DOLocationID', '239')     |  107804.0000 |
| ('DOLocationID', '162')     |  104656.0000 |
| ('DOLocationID', '141')     |  100319.0000 |
| ('DOLocationID', '68')      |   97921.0000 |
| ('DOLocationID', '234')     |   91489.0000 |
| ('DOLocationID', '163')     |   91274.0000 |
| ('DOLocationID', '79')      |   90723.0000 |
| ('DOLocationID', '238')     |   88091.0000 |
| ('DOLocationID', '48')      |   87034.0000 |
| ('DOLocationID', '246')     |   82612.0000 |
| ('DOLocationID', '263')     |   82001.0000 |
| ('DOLocationID', '140')     |   79371.0000 |
| ('DOLocationID', '229')     |   78312.0000 |
| ('DOLocationID', '186')     |   76263.0000 |

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

- 파일명 기준 연월: `2026-05`
- 실제 연월 수: 5
- 여러 연월 혼재: True
- 정제 후 기준 연월 밖 행: 14

| tpep_pickup_datetime   |         rows |
|:-----------------------|-------------:|
| 2008-12                |  1           |
| 2009-01                |  1           |
| 2026-04                | 11           |
| 2026-05                |  4.09082e+06 |
| 2026-06                |  1           |

분석 대상을 2026-05로 한정하면 `is_outside_source_month == False`인 행을 주 분석에 사용합니다. 정제 후 확인된 기준 연월 밖 14행은 데이터 준비 단계에서 삭제하지 않았으며, 포함 여부는 후속 분석 목적에 따라 결정하고 필요하면 포함·제외 결과를 비교합니다.

## Pandas와 Polars의 단계별 정제 결과 비교

|                                               |           Pandas |           Polars |
|:----------------------------------------------|-----------------:|-----------------:|
| raw_rows                                      |      4.09084e+06 |      4.09084e+06 |
| duplicate_rows_removed                        |      0           |      0           |
| core_missing_rows_removed                     |      0           |      0           |
| invalid_datetime_rows_removed                 |      0           |      0           |
| nonpositive_duration_rows                     |  52063           |  52063           |
| nonpositive_distance_rows                     | 113031           | 113031           |
| nonpositive_fare_rows                         |  17182           |  17182           |
| nonpositive_duration_distance_or_fare_removed | 178950           | 178950           |
| cleaned_rows                                  |      3.91189e+06 |      3.91189e+06 |

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
| morning_rush     |  414334.0000 |     10.5917 |
| evening_rush     |  652022.0000 |     16.6677 |
| weekday_non_rush | 1604854.0000 |     41.0251 |
| weekend          | 1240676.0000 |     31.7155 |

주 비교 집단은 `weekday_rush`와 `weekday_non_rush`이며 주말은 비교 집단에서 제외합니다.

## 평일 출퇴근·비출퇴근 핵심 변수 기초 통계

|                                           |        count |    mean |       std |    min |     25% |     50% |     75% |          max |
|:------------------------------------------|-------------:|--------:|----------:|-------:|--------:|--------:|--------:|-------------:|
| ('weekday_rush', 'trip_duration_min')     | 1066356.0000 | 19.8801 |   26.4424 | 0.0167 |  8.7333 | 14.5667 | 23.9167 |    6082.4667 |
| ('weekday_rush', 'fare_amount')           | 1066356.0000 | 21.0425 |   17.5300 | 0.0100 | 10.0000 | 15.6000 | 25.4400 |     888.0000 |
| ('weekday_rush', 'trip_distance')         | 1066356.0000 |  4.8158 |  397.6353 | 0.0100 |  1.0100 |  1.7700 |  3.4900 |  165549.1000 |
| ('weekday_rush', 'fare_per_mile')         | 1066356.0000 | 49.0800 |  384.2843 | 0.0000 |  6.1937 |  8.0296 | 10.4012 |   25000.0000 |
| ('weekday_rush', 'average_speed_mph')     | 1066356.0000 | 15.1853 | 1872.4229 | 0.0029 |  6.1630 |  8.2510 | 11.2131 | 1486310.9000 |
| ('weekday_non_rush', 'trip_duration_min') | 1604854.0000 | 19.7966 |   25.9513 | 0.0167 |  9.3000 | 15.2833 | 24.2833 |    4344.1000 |
| ('weekday_non_rush', 'fare_amount')       | 1604854.0000 | 22.1823 |   17.8615 | 0.0100 | 10.7000 | 16.7900 | 27.5000 |     881.5000 |
| ('weekday_non_rush', 'trip_distance')     | 1604854.0000 |  5.0890 |  493.8538 | 0.0100 |  1.1000 |  1.9700 |  4.0900 |  307491.4700 |
| ('weekday_non_rush', 'fare_per_mile')     | 1604854.0000 | 14.0532 |  170.1970 | 0.0000 |  5.7664 |  7.7990 | 10.4615 |   65500.0000 |
| ('weekday_non_rush', 'average_speed_mph') | 1604854.0000 | 15.7686 | 1928.3541 | 0.0004 |  6.1979 |  8.7429 | 12.3913 | 1487840.5800 |

이 표는 후속 시각화와 통계 검정을 위한 데이터 품질 확인이며 평균 차이만으로 결론을 내리지 않습니다.

## 보존된 이상치 후보

|                                |   rows |
|:-------------------------------|-------:|
| is_long_trip_candidate         |     23 |
| is_large_distance_candidate    |     73 |
| is_large_fare_candidate        |      2 |
| is_invalid_passenger_candidate |  12068 |

이상치 후보 플래그는 데이터 오류를 확정한 값이 아니며, 이번 전처리 단계에서는 후보 행을 임의로 제거하지 않았습니다.

## 정제 및 EDA 실행 시간 비교

|               |    Pandas |   Polars |
|:--------------|----------:|---------:|
| eda_seconds   | 10.447213 | 2.062992 |
| clean_seconds | 10.763426 | 1.423890 |

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