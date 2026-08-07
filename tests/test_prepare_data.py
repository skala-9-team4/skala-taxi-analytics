# 작성자: 최지윤
# 작성 목적: [종합실습 2] 데이터 로딩·날짜 검증·정제·EDA 품질 집계 동작을 회귀 테스트
# 작성일: 2026-08-07
#
# 변경사항 내역 (날짜, 변경목적, 변경내용 순)
# 2026-08-07 : [회귀 검증 추가] CSV·Parquet 입력, Pandas·Polars 표본 일치, 전처리 및 오류 후보 보존 테스트를 추가
# 2026-08-07 : [CLI 기본 입력 검증] 인수 생략 시 기본 경로와 사용자 지정 경로 선택 및 파일 부재 오류를 검증

from pathlib import Path

import pandas as pd
import pytest

from src.prepare_data import (
    DEFAULT_INPUT,
    PRESERVE_COLUMNS,
    clean_data,
    expected_month,
    inspect_date_range,
    load_frames,
    main,
    parse_args,
    summarize_categories,
    validate_loads,
    verify,
)


def base_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "VendorID": [1, 2],
            "tpep_pickup_datetime": ["2025-01-01 08:00:00", "2025-01-01 09:00:00"],
            "tpep_dropoff_datetime": ["2025-01-01 08:30:00", "2025-01-01 09:45:00"],
            "passenger_count": [1, 2],
            "trip_distance": [3.0, 5.0],
            "RatecodeID": [1, 1],
            "store_and_fwd_flag": ["N", "Y"],
            "PULocationID": [10, 20],
            "DOLocationID": [30, 40],
            "fare_amount": [15.0, 20.0],
            "total_amount": [18.0, 24.0],
            "extra": [0.0, 1.0],
        }
    )


def test_csv_dates_are_stored_as_datetime_and_used_for_duration(tmp_path: Path) -> None:
    source = tmp_path / "yellow_tripdata_2025-01.csv"
    frame = base_frame()
    frame.loc[1, "tpep_pickup_datetime"] = "not-a-date"
    frame.to_csv(source, index=False)

    pandas_df, polars_df, _ = load_frames(source)

    assert pd.api.types.is_datetime64_any_dtype(pandas_df["tpep_pickup_datetime"])
    assert pd.isna(pandas_df.loc[1, "tpep_pickup_datetime"])
    assert polars_df["tpep_pickup_datetime"].null_count() == 1
    cleaned_df, metrics = clean_data(pandas_df, source)
    assert cleaned_df["trip_duration_min"].tolist() == [30.0]
    assert metrics["core_missing_rows_removed"] == 1


def test_parquet_load_and_pandas_polars_sample_values_match(tmp_path: Path) -> None:
    source = tmp_path / "yellow_tripdata_2025-01.parquet"
    frame = base_frame()
    frame["tpep_pickup_datetime"] = pd.to_datetime(frame["tpep_pickup_datetime"])
    frame["tpep_dropoff_datetime"] = pd.to_datetime(frame["tpep_dropoff_datetime"])
    frame.to_parquet(source, index=False)

    pandas_df, polars_df, comparison = load_frames(source)
    result = validate_loads(pandas_df, polars_df)

    assert result["matched"] is True
    assert result["indices"] == [0, 1]
    assert comparison.loc["rows"].tolist() == [2, 2]


def test_expected_month_and_actual_month_detection() -> None:
    pickup = pd.Series(pd.to_datetime(["2025-01-01", "2025-02-01"]))

    assert expected_month(Path("yellow_tripdata_2025-01.parquet")) == pd.Period("2025-01")
    assert expected_month(Path("yellow_taxi.csv")) is None
    named = inspect_date_range(pickup, Path("yellow_tripdata_2025-01.parquet"))
    unnamed = inspect_date_range(pickup, Path("yellow_taxi.csv"))
    assert named["has_multiple_months"] is True
    assert named["outside_source_month_rows"] == 1
    assert unnamed["source_month"] is None
    assert unnamed["outside_source_month_rows"] is None
    assert unnamed["actual_month_count"] == 2


def test_missing_required_column_raises_clear_error() -> None:
    with pytest.raises(ValueError, match="필수 컬럼.*fare_amount"):
        clean_data(base_frame().drop(columns="fare_amount"), Path("sample.csv"))


def test_cleaning_removes_only_full_duplicates_core_missing_and_invalid_trips() -> None:
    valid = base_frame().iloc[[0]].copy()
    rows = [
        valid,
        valid.copy(),
        valid.assign(extra=1.0),
        valid.assign(trip_distance=None),
        valid.assign(tpep_dropoff_datetime="2025-01-01 07:59:00"),
        valid.assign(trip_distance=0.0),
        valid.assign(fare_amount=0.0),
    ]
    raw_df = pd.concat(rows, ignore_index=True)

    cleaned_df, metrics = clean_data(raw_df, Path("yellow_tripdata_2025-01.csv"))

    assert len(cleaned_df) == 2
    assert metrics["duplicate_rows_removed"] == 1
    assert metrics["core_missing_rows_removed"] == 1
    assert metrics["nonpositive_duration_distance_or_fare_removed"] == 3
    assert cleaned_df["trip_duration_min"].tolist() == [30.0, 30.0]
    assert PRESERVE_COLUMNS.intersection(raw_df.columns) <= set(cleaned_df.columns)
    verify(raw_df, cleaned_df)


def test_error_candidates_are_flagged_and_preserved() -> None:
    raw_df = pd.concat(
        [
            base_frame().iloc[[0]].assign(tpep_dropoff_datetime="2025-01-02 08:01:00"),
            base_frame().iloc[[0]].assign(trip_distance=201.0),
            base_frame().iloc[[0]].assign(fare_amount=1001.0),
            base_frame().iloc[[0]].assign(passenger_count=0),
        ],
        ignore_index=True,
    )

    cleaned_df, _ = clean_data(raw_df, Path("yellow_tripdata_2025-01.parquet"))

    assert len(cleaned_df) == 4
    assert cleaned_df["is_long_trip_candidate"].sum() == 1
    assert cleaned_df["is_large_distance_candidate"].sum() == 1
    assert cleaned_df["is_large_fare_candidate"].sum() == 1
    assert cleaned_df["is_invalid_passenger_candidate"].sum() == 1


def test_category_distribution_has_frequency_ratio_and_missing_count() -> None:
    raw_df = pd.DataFrame({"store_and_fwd_flag": ["N", "N", "Y", None]})

    summary = summarize_categories(raw_df)

    assert summary.loc[("store_and_fwd_flag", "N"), "count"] == 2
    assert summary.loc[("store_and_fwd_flag", "N"), "ratio_pct"] == 50.0
    assert summary.loc[("store_and_fwd_flag", "N"), "unique_count"] == 3
    assert summary.loc[("store_and_fwd_flag", "N"), "missing_count"] == 1


def test_unsupported_input_format_raises_clear_error(tmp_path: Path) -> None:
    source = tmp_path / "taxi.json"
    source.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="지원 형식"):
        load_frames(source)


def test_cli_uses_default_or_user_supplied_input(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["prepare_data.py"])
    assert parse_args().input == DEFAULT_INPUT

    monkeypatch.setattr("sys.argv", ["prepare_data.py", "data/raw/other.parquet"])
    assert parse_args().input == Path("data/raw/other.parquet")


def test_cli_missing_input_names_required_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    missing = tmp_path / "missing.parquet"
    monkeypatch.setattr("sys.argv", ["prepare_data.py", str(missing)])
    with pytest.raises(FileNotFoundError, match=str(missing)):
        main()
