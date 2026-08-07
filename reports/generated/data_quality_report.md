# 데이터 품질 및 전처리 결과

- 원본: `data/raw/yellow_tripdata_2025-01.parquet`
- 크기: 3,475,226행 × 20열
- 완전 중복: 0행 (0.0000%)
- Pandas/Polars 로딩 일관성: 통과 (크기, 컬럼 순서, 결측치 수, 표본 실제 값)
- 값 비교 표본: 앞·뒤 각 최대 5행과 seed=42 고정 표본, 주요 11개 컬럼, 총 15행
- 로딩 시간: 각 라이브러리 1회 측정 참고값 (OS 파일 캐시에 따라 변동)

## Pandas와 Polars 비교

|              |      Pandas |      Polars |
|:-------------|------------:|------------:|
| load_seconds |       0.216 |       0.126 |
| rows         | 3475226.000 | 3475226.000 |
| columns      |      20.000 |      20.000 |
| memory_mb    |     493.470 |     467.449 |

### Pandas dtype

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

### Polars dtype

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

### Pandas 앞 5행

|   VendorID | tpep_pickup_datetime   | tpep_dropoff_datetime   |   passenger_count |   trip_distance |   RatecodeID | store_and_fwd_flag   |   PULocationID |   DOLocationID |   payment_type |   fare_amount |   extra |   mta_tax |   tip_amount |   tolls_amount |   improvement_surcharge |   total_amount |   congestion_surcharge |   Airport_fee |   cbd_congestion_fee |
|-----------:|:-----------------------|:------------------------|------------------:|----------------:|-------------:|:---------------------|---------------:|---------------:|---------------:|--------------:|--------:|----------:|-------------:|---------------:|------------------------:|---------------:|-----------------------:|--------------:|---------------------:|
|          1 | 2025-01-01 00:18:38    | 2025-01-01 00:26:59     |                 1 |            1.6  |            1 | N                    |            229 |            237 |              1 |          10   |     3.5 |       0.5 |         3    |              0 |                       1 |          18    |                    2.5 |             0 |                    0 |
|          1 | 2025-01-01 00:32:40    | 2025-01-01 00:35:13     |                 1 |            0.5  |            1 | N                    |            236 |            237 |              1 |           5.1 |     3.5 |       0.5 |         2.02 |              0 |                       1 |          12.12 |                    2.5 |             0 |                    0 |
|          1 | 2025-01-01 00:44:04    | 2025-01-01 00:46:01     |                 1 |            0.6  |            1 | N                    |            141 |            141 |              1 |           5.1 |     3.5 |       0.5 |         2    |              0 |                       1 |          12.1  |                    2.5 |             0 |                    0 |
|          2 | 2025-01-01 00:14:27    | 2025-01-01 00:20:01     |                 3 |            0.52 |            1 | N                    |            244 |            244 |              2 |           7.2 |     1   |       0.5 |         0    |              0 |                       1 |           9.7  |                    0   |             0 |                    0 |
|          2 | 2025-01-01 00:21:34    | 2025-01-01 00:25:06     |                 3 |            0.66 |            1 | N                    |            244 |            116 |              2 |           5.8 |     1   |       0.5 |         0    |              0 |                       1 |           8.3  |                    0   |             0 |                    0 |

### Polars 앞 5행

|   VendorID | tpep_pickup_datetime   | tpep_dropoff_datetime   |   passenger_count |   trip_distance |   RatecodeID | store_and_fwd_flag   |   PULocationID |   DOLocationID |   payment_type |   fare_amount |   extra |   mta_tax |   tip_amount |   tolls_amount |   improvement_surcharge |   total_amount |   congestion_surcharge |   Airport_fee |   cbd_congestion_fee |
|-----------:|:-----------------------|:------------------------|------------------:|----------------:|-------------:|:---------------------|---------------:|---------------:|---------------:|--------------:|--------:|----------:|-------------:|---------------:|------------------------:|---------------:|-----------------------:|--------------:|---------------------:|
|          1 | 2025-01-01 00:18:38    | 2025-01-01 00:26:59     |                 1 |            1.6  |            1 | N                    |            229 |            237 |              1 |          10   |     3.5 |       0.5 |         3    |              0 |                       1 |          18    |                    2.5 |             0 |                    0 |
|          1 | 2025-01-01 00:32:40    | 2025-01-01 00:35:13     |                 1 |            0.5  |            1 | N                    |            236 |            237 |              1 |           5.1 |     3.5 |       0.5 |         2.02 |              0 |                       1 |          12.12 |                    2.5 |             0 |                    0 |
|          1 | 2025-01-01 00:44:04    | 2025-01-01 00:46:01     |                 1 |            0.6  |            1 | N                    |            141 |            141 |              1 |           5.1 |     3.5 |       0.5 |         2    |              0 |                       1 |          12.1  |                    2.5 |             0 |                    0 |
|          2 | 2025-01-01 00:14:27    | 2025-01-01 00:20:01     |                 3 |            0.52 |            1 | N                    |            244 |            244 |              2 |           7.2 |     1   |       0.5 |         0    |              0 |                       1 |           9.7  |                    0   |             0 |                    0 |
|          2 | 2025-01-01 00:21:34    | 2025-01-01 00:25:06     |                 3 |            0.66 |            1 | N                    |            244 |            116 |              2 |           5.8 |     1   |       0.5 |         0    |              0 |                       1 |           8.3  |                    0   |             0 |                    0 |

## 결측치

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

## 주요 수치형 기초 통계

|                 |       count |   mean |     std |      min |    25% |    50% |    75% |        max |
|:----------------|------------:|-------:|--------:|---------:|-------:|-------:|-------:|-----------:|
| trip_distance   | 3475226.000 |  5.855 | 564.602 |    0.000 |  0.980 |  1.670 |  3.100 | 276423.570 |
| fare_amount     | 3475226.000 | 17.082 | 463.473 | -900.000 |  8.600 | 12.110 | 19.500 | 863372.120 |
| total_amount    | 3475226.000 | 25.611 | 463.658 | -901.000 | 15.200 | 19.950 | 27.780 | 863380.370 |
| extra           | 3475226.000 |  1.318 |   1.862 |   -7.500 |  0.000 |  0.000 |  2.500 |     15.000 |
| passenger_count | 2935077.000 |  1.298 |   0.751 |    0.000 |  1.000 |  1.000 |  1.000 |      9.000 |

## 날짜 범위

|                       | min                        | max                        |
|:----------------------|:---------------------------|:---------------------------|
| tpep_pickup_datetime  | 2024-12-31T20:47:55.000000 | 2025-02-01T00:00:44.000000 |
| tpep_dropoff_datetime | 2024-12-18T07:52:40.000000 | 2025-02-01T23:44:11.000000 |

## 범주형 주요 값 분포 (각 상위 20개)

|                             |        count |   ratio_pct |   unique_count |   missing_count |
|:----------------------------|-------------:|------------:|---------------:|----------------:|
| ('store_and_fwd_flag', 'N') | 2927431.0000 |     84.2371 |         3.0000 |     540149.0000 |
| ('store_and_fwd_flag', nan) |  540149.0000 |     15.5428 |         3.0000 |     540149.0000 |
| ('store_and_fwd_flag', 'Y') |    7646.0000 |      0.2200 |         3.0000 |     540149.0000 |

## 주요 코드 분포 (각 상위 20개)

|                         |            count |
|:------------------------|-----------------:|
| ('VendorID', 2.0)       |      2.71986e+06 |
| ('VendorID', 1.0)       | 753671           |
| ('VendorID', 7.0)       |   1206           |
| ('VendorID', 6.0)       |    489           |
| ('RatecodeID', 1.0)     |      2.75647e+06 |
| ('RatecodeID', nan)     | 540149           |
| ('RatecodeID', 2.0)     |  94420           |
| ('RatecodeID', 99.0)    |  41963           |
| ('RatecodeID', 5.0)     |  26501           |
| ('RatecodeID', 3.0)     |   8622           |
| ('RatecodeID', 4.0)     |   7092           |
| ('RatecodeID', 6.0)     |      7           |
| ('PULocationID', 161.0) | 169977           |
| ('PULocationID', 237.0) | 163703           |
| ('PULocationID', 236.0) | 155647           |
| ('PULocationID', 132.0) | 146137           |
| ('PULocationID', 230.0) | 125829           |
| ('PULocationID', 186.0) | 119131           |
| ('PULocationID', 162.0) | 117930           |
| ('PULocationID', 142.0) | 110585           |
| ('PULocationID', 239.0) |  96614           |
| ('PULocationID', 163.0) |  95906           |
| ('PULocationID', 234.0) |  95896           |
| ('PULocationID', 170.0) |  95636           |
| ('PULocationID', 68.0)  |  91241           |
| ('PULocationID', 138.0) |  89658           |
| ('PULocationID', 48.0)  |  84137           |
| ('PULocationID', 141.0) |  81661           |
| ('PULocationID', 79.0)  |  81576           |
| ('PULocationID', 249.0) |  77355           |
| ('PULocationID', 164.0) |  76066           |
| ('PULocationID', 140.0) |  75093           |
| ('DOLocationID', 236.0) | 161376           |
| ('DOLocationID', 237.0) | 149970           |
| ('DOLocationID', 161.0) | 131258           |
| ('DOLocationID', 230.0) | 108177           |
| ('DOLocationID', 170.0) | 100060           |
| ('DOLocationID', 142.0) |  98982           |
| ('DOLocationID', 239.0) |  97559           |
| ('DOLocationID', 162.0) |  93798           |
| ('DOLocationID', 141.0) |  92675           |
| ('DOLocationID', 68.0)  |  89232           |
| ('DOLocationID', 234.0) |  84669           |
| ('DOLocationID', 163.0) |  84631           |
| ('DOLocationID', 48.0)  |  82722           |
| ('DOLocationID', 238.0) |  78467           |
| ('DOLocationID', 186.0) |  76338           |
| ('DOLocationID', 79.0)  |  76009           |
| ('DOLocationID', 140.0) |  74165           |
| ('DOLocationID', 263.0) |  73889           |
| ('DOLocationID', 164.0) |  72594           |
| ('DOLocationID', 229.0) |  71480           |

## 기준 연월 및 실제 날짜 분포

- 파일명 기준 연월: `2025-01`
- 실제 연월 수: 3
- 여러 연월 혼재: True
- 기준 연월 밖 행: 22

| tpep_pickup_datetime   |        rows |
|:-----------------------|------------:|
| 2024-12                | 21          |
| 2025-01                |  3.4752e+06 |
| 2025-02                |  1          |

## 처리 전후

|                                               |            count |
|:----------------------------------------------|-----------------:|
| raw_rows                                      |      3.47523e+06 |
| duplicate_rows_removed                        |      0           |
| core_missing_rows_removed                     |      0           |
| invalid_datetime_rows_removed                 |      0           |
| nonpositive_duration_rows                     |   2051           |
| nonpositive_distance_rows                     |  90893           |
| nonpositive_fare_rows                         | 145516           |
| nonpositive_duration_distance_or_fare_removed | 222712           |
| cleaned_rows                                  |      3.25251e+06 |

## 보존된 오류 후보

|                                |   rows |
|:-------------------------------|-------:|
| is_long_trip_candidate         |     13 |
| is_large_distance_candidate    |    101 |
| is_large_fare_candidate        |      3 |
| is_invalid_passenger_candidate |  23635 |
| is_outside_source_month        |     22 |

후보 기준은 절대적인 오류 판정이 아닌 보수적인 임시 검토 기준이므로 삭제하지 않았습니다. `is_rush_hour`는 팀 기준 확정 후 생성합니다.