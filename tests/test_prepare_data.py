# 작성자: 최지윤
# 작성 목적: [종합실습 2] 데이터 로딩·날짜 검증·정제·EDA 품질 집계 동작을 회귀 테스트
# 작성일: 2026-08-07
#
# 변경사항 내역
# 2026-08-08:
# - Pandas·Polars의 순차 로딩, 결측·중복·정제·EDA 및 파생 변수 동등성 검증을 보완
# - 시간대 목록 순서와 무관한 경계 분류, 품질 요약 컬럼, 비교 집단·품질 집계를 검증
# - 비교 불일치와 단계별 예외에서 보고서·최종 결과 보존 및 임시 파일 정리를 검증

import inspect
from pathlib import Path

import pandas as pd
import polars as pl
import pytest

from src import prepare_data
from src.prepare_data import (
    CANDIDATE_COLUMNS,
    DEFAULT_INPUT,
    EDA_CHECKS,
    LOAD_SAMPLE_COLUMNS,
    QUALITY_SUMMARY_COLUMNS,
    SOURCE_MONTH_FLAG,
    clean_data,
    clean_polars_data,
    cleaned_quality_pandas,
    cleaned_quality_polars,
    compare_aggregates,
    compare_results,
    expected_month,
    inspect_date_range,
    load_one,
    main,
    make_eda,
    make_polars_eda,
    normalize_code_value,
    pandas_load_signature,
    parse_args,
    summarize_categories,
    validate_analysis_groups,
    validate_polars_signature,
    verify,
    write_report,
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

    pandas_df, _, _ = load_one(source, "Pandas")
    signature = pandas_load_signature(pandas_df)
    assert pd.api.types.is_datetime64_any_dtype(pandas_df["tpep_pickup_datetime"])
    assert pd.isna(pandas_df.loc[1, "tpep_pickup_datetime"])
    cleaned_df, metrics = clean_data(pandas_df, source)
    assert cleaned_df["trip_duration_min"].tolist() == [30.0]
    assert metrics["core_missing_rows_removed"] == 1
    del pandas_df

    polars_df, _, _ = load_one(source, "Polars")
    assert polars_df["tpep_pickup_datetime"].null_count() == 1
    assert validate_polars_signature(signature, polars_df)["matched"] is True


def test_parquet_load_and_pandas_polars_sample_values_match(tmp_path: Path) -> None:
    source = tmp_path / "yellow_tripdata_2025-01.parquet"
    frame = base_frame()
    frame["tpep_pickup_datetime"] = pd.to_datetime(frame["tpep_pickup_datetime"])
    frame["tpep_dropoff_datetime"] = pd.to_datetime(frame["tpep_dropoff_datetime"])
    frame.to_parquet(source, index=False)

    pandas_df, pandas_load, _ = load_one(source, "Pandas")
    signature = pandas_load_signature(pandas_df)
    del pandas_df
    polars_df, polars_load, _ = load_one(source, "Polars")
    result = validate_polars_signature(signature, polars_df)

    assert result["matched"] is True
    assert result["indices"] == [0, 1]
    assert pandas_load["rows"] == polars_load["rows"] == 2
    assert pandas_load["columns"] == polars_load["columns"] == len(frame.columns)


@pytest.mark.parametrize("difference", ["shape", "columns", "missing", "sample"])
def test_sequential_load_validation_detects_mismatch(difference: str) -> None:
    pandas_df = base_frame()
    signature = pandas_load_signature(pandas_df)
    polars_df = pl.from_pandas(pandas_df)
    if difference == "shape":
        polars_df = polars_df.head(1)
    elif difference == "columns":
        polars_df = polars_df.rename({"VendorID": "vendor"})
    elif difference == "missing":
        polars_df = polars_df.with_columns(pl.lit(None).cast(pl.Float64).alias("trip_distance"))
    else:
        polars_df = polars_df.with_columns((pl.col("fare_amount") + 1).alias("fare_amount"))

    with pytest.raises(AssertionError):
        validate_polars_signature(signature, polars_df)


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
    assert LOAD_SAMPLE_COLUMNS.intersection(raw_df.columns) <= set(cleaned_df.columns)
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


def test_category_distribution_contains_only_frequency_and_ratio() -> None:
    raw_df = pd.DataFrame({"store_and_fwd_flag": ["N", "N", "Y", None]})

    summary = summarize_categories(raw_df)

    assert summary.loc[("store_and_fwd_flag", "N"), "count"] == 2
    assert summary.loc[("store_and_fwd_flag", "N"), "ratio_pct"] == 50.0
    assert summary.columns.tolist() == ["count", "ratio_pct"]


def test_pandas_polars_category_distribution_structures_match() -> None:
    frame = base_frame()
    for column in ["tpep_pickup_datetime", "tpep_dropoff_datetime"]:
        frame[column] = pd.to_datetime(frame[column])
    pandas_eda = make_eda(frame)
    polars_eda = make_polars_eda(pl.from_pandas(frame))

    assert pandas_eda["category_distribution"].columns.tolist() == ["count", "ratio_pct"]
    assert polars_eda["category_distribution"].columns.tolist() == ["count", "ratio_pct"]
    assert compare_aggregates(pandas_eda["category_distribution"], polars_eda["category_distribution"])[0]


@pytest.mark.parametrize("library", ["Pandas", "Polars"])
def test_unsupported_input_format_raises_clear_error(tmp_path: Path, library: str) -> None:
    source = tmp_path / "taxi.json"
    source.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="지원 형식"):
        load_one(source, library)


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


def paired_results(frame: pd.DataFrame):
    pandas_frame = frame.copy()
    for column in ["tpep_pickup_datetime", "tpep_dropoff_datetime"]:
        pandas_frame[column] = pd.to_datetime(pandas_frame[column], errors="coerce")
    polars_frame = pl.from_pandas(pandas_frame)
    pandas_eda, polars_eda = make_eda(pandas_frame), make_polars_eda(polars_frame)
    pandas_cleaned, pandas_metrics = clean_data(pandas_frame, Path("yellow_tripdata_2025-01.csv"))
    polars_cleaned, polars_metrics = clean_polars_data(polars_frame, Path("yellow_tripdata_2025-01.csv"))
    return pandas_eda, polars_eda, pandas_cleaned, polars_cleaned, pandas_metrics, polars_metrics


def compare_paired_results(results: tuple[object, ...]) -> dict[str, object]:
    pandas_eda, polars_eda, pandas_cleaned, polars_cleaned, pandas_metrics, polars_metrics = results
    return compare_results(
        pandas_eda,
        polars_eda,
        pandas_metrics,
        polars_metrics,
        cleaned_quality_pandas(pandas_cleaned),
        cleaned_quality_polars(polars_cleaned),
    )


def test_pandas_polars_cleaning_and_derived_values_match() -> None:
    valid = base_frame().iloc[[0]]
    frame = pd.concat([
        valid,
        valid.copy(),
        valid.assign(extra=2.0),
        valid.assign(trip_distance=None),
        valid.assign(tpep_dropoff_datetime="invalid"),
        valid.assign(tpep_dropoff_datetime="2025-01-01 07:59:00"),
        valid.assign(trip_distance=0.0),
        valid.assign(fare_amount=-1.0),
    ], ignore_index=True)

    results = paired_results(frame)
    comparison = compare_paired_results(results)

    assert comparison["matched"] is True
    assert results[2]["trip_duration_min"].tolist() == [30.0, 30.0]
    assert results[2]["pickup_hour"].tolist() == [8, 8]
    assert results[2]["day_of_week"].tolist() == ["Wednesday", "Wednesday"]
    assert results[2]["is_weekday"].all()
    assert results[4] == results[5]


def test_polars_treats_nan_and_null_as_missing_and_keeps_duplicate_order() -> None:
    pandas_frame = base_frame().iloc[[0, 1, 0]].copy()
    pandas_frame.loc[pandas_frame.index[1], "trip_distance"] = float("nan")
    for column in ["tpep_pickup_datetime", "tpep_dropoff_datetime"]:
        pandas_frame[column] = pd.to_datetime(pandas_frame[column])
    polars_frame = pl.from_pandas(pandas_frame, nan_to_null=False)

    pandas_cleaned, pandas_metrics = clean_data(pandas_frame, Path("sample.csv"))
    polars_cleaned, polars_metrics = clean_polars_data(polars_frame, Path("sample.csv"))

    assert pandas_metrics == polars_metrics
    assert pandas_cleaned["VendorID"].tolist() == polars_cleaned["VendorID"].to_list() == [1]


def test_eda_matches_despite_dtype_and_null_representation() -> None:
    pandas_frame = base_frame().assign(passenger_count=pd.Series([1.0, float("nan")]))
    for column in ["tpep_pickup_datetime", "tpep_dropoff_datetime"]:
        pandas_frame[column] = pd.to_datetime(pandas_frame[column])
    polars_frame = pl.from_pandas(pandas_frame, nan_to_null=False).with_columns(pl.col("VendorID").cast(pl.Float64))

    pandas_eda, polars_eda = make_eda(pandas_frame), make_polars_eda(polars_frame)

    assert pandas_eda["missing"]["missing_count"].to_dict() == polars_eda["missing"]["missing_count"].to_dict()
    pd.testing.assert_frame_equal(
        pandas_eda["numeric_summary"], polars_eda["numeric_summary"],
        check_dtype=False, check_exact=False, rtol=1e-9, atol=1e-9,
    )


def test_meaningful_value_difference_is_detected() -> None:
    results = list(paired_results(base_frame()))
    results[3] = results[3].with_columns((pl.col("fare_amount") + 1).alias("fare_amount"))

    comparison = compare_paired_results(tuple(results))

    assert comparison["matched"] is False
    assert "정제 결과 표본·파생 변수" in comparison["differences"]


def rush_boundary_frame() -> pd.DataFrame:
    pickups = pd.to_datetime([
        "2025-01-06 05:59", "2025-01-06 06:00", "2025-01-06 09:59", "2025-01-06 10:00",
        "2025-01-06 15:59", "2025-01-06 16:00", "2025-01-06 19:59", "2025-01-06 20:00",
        "2025-01-11 06:00", "2025-01-11 16:00",
    ])
    row = base_frame().iloc[[0]]
    return pd.concat([
        row.assign(tpep_pickup_datetime=pickup, tpep_dropoff_datetime=pickup + pd.Timedelta(minutes=30))
        for pickup in pickups
    ], ignore_index=True)


def test_rush_hour_boundaries_weekend_and_polars_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame = rush_boundary_frame()
    monkeypatch.setattr(prepare_data, "RUSH_PERIODS", list(reversed(prepare_data.RUSH_PERIODS)))
    pandas_cleaned, _ = clean_data(frame, Path("sample.csv"))
    polars_cleaned, _ = clean_polars_data(pl.from_pandas(frame), Path("sample.csv"))

    expected_rush = [False, True, True, False, False, True, True, False, False, False]
    expected_period = [
        "weekday_non_rush", "morning_rush", "morning_rush", "weekday_non_rush",
        "weekday_non_rush", "evening_rush", "evening_rush", "weekday_non_rush",
        "weekend", "weekend",
    ]
    assert pandas_cleaned["is_rush_hour"].tolist() == expected_rush
    assert pandas_cleaned["rush_period"].tolist() == expected_period
    assert polars_cleaned["is_rush_hour"].to_list() == expected_rush
    assert polars_cleaned["rush_period"].to_list() == expected_period
    assert pandas_cleaned.loc[8:, "weekday_comparison_group"].isna().all()
    assert polars_cleaned["weekday_comparison_group"].to_list()[8:] == [None, None]


def test_rate_and_speed_derivatives_match() -> None:
    pandas_cleaned, _ = clean_data(base_frame(), Path("sample.csv"))
    polars_cleaned, _ = clean_polars_data(pl.from_pandas(base_frame()), Path("sample.csv"))

    assert pandas_cleaned["fare_per_mile"].tolist() == pytest.approx([5.0, 4.0])
    assert pandas_cleaned["average_speed_mph"].tolist() == pytest.approx([6.0, 20 / 3])
    assert polars_cleaned["fare_per_mile"].to_list() == pytest.approx(pandas_cleaned["fare_per_mile"])
    assert polars_cleaned["average_speed_mph"].to_list() == pytest.approx(pandas_cleaned["average_speed_mph"])
    assert QUALITY_SUMMARY_COLUMNS == [
        "trip_duration_min",
        "fare_amount",
        "trip_distance",
        "fare_per_mile",
        "average_speed_mph",
    ]


def test_outside_source_month_and_comparison_groups_match_in_polars() -> None:
    frame = rush_boundary_frame().iloc[[1, 3, 8]].copy()
    frame.loc[frame.index[1], "tpep_pickup_datetime"] = pd.Timestamp("2025-02-03 12:00")
    frame.loc[frame.index[1], "tpep_dropoff_datetime"] = pd.Timestamp("2025-02-03 12:30")

    pandas_cleaned, _ = clean_data(frame, Path("yellow_tripdata_2025-01.csv"))
    polars_cleaned, _ = clean_polars_data(pl.from_pandas(frame), Path("yellow_tripdata_2025-01.csv"))

    assert pandas_cleaned["is_outside_source_month"].tolist() == [False, True, False]
    assert polars_cleaned["is_outside_source_month"].to_list() == [False, True, False]
    pandas_quality = cleaned_quality_pandas(pandas_cleaned)
    polars_quality = cleaned_quality_polars(polars_cleaned)
    assert SOURCE_MONTH_FLAG not in pandas_quality["candidate_counts"].index
    assert SOURCE_MONTH_FLAG not in polars_quality["candidate_counts"].index
    assert pandas_quality["source_month_count"] == polars_quality["source_month_count"] == 1
    assert pandas_cleaned["weekday_comparison_group"].tolist()[:2] == ["weekday_rush", "weekday_non_rush"]
    assert polars_cleaned["weekday_comparison_group"].to_list() == ["weekday_rush", "weekday_non_rush", None]


def test_compare_results_accepts_quality_aggregates_without_cleaned_frames() -> None:
    results = paired_results(rush_boundary_frame())
    parameter_names = list(inspect.signature(compare_results).parameters)
    comparison = compare_paired_results(results)

    assert parameter_names == [
        "pandas_eda", "polars_eda", "pandas_metrics", "polars_metrics",
        "pandas_quality", "polars_quality",
    ]
    assert set(comparison["checks"]) == {
        *EDA_CHECKS,
        "출퇴근 분류 분포", "평일 출퇴근·비출퇴근 통계", "단계별 제거 행 수",
        "이상치 후보 집계", "분석 기간 플래그 집계", "최종 컬럼 순서",
        "정제 결과 표본·파생 변수",
    }
    assert comparison["matched"] is True


def test_aggregate_comparison_keeps_index_and_category_names() -> None:
    left = pd.DataFrame({"count": [2]}, index=pd.Index(["morning_rush"], name="rush_period"))
    different_value = pd.DataFrame({"count": [2]}, index=pd.Index(["evening_rush"], name="rush_period"))
    different_name = left.rename_axis("other_group")

    assert compare_aggregates(left, different_value)[0] is False
    assert compare_aggregates(left, different_name)[0] is False


def test_code_integer_and_float_labels_normalize_equally() -> None:
    assert normalize_code_value(1) == normalize_code_value(1.0) == "1"
    pandas_eda = make_eda(base_frame().assign(RatecodeID=[1.0, 2.0]))
    polars_eda = make_polars_eda(pl.from_pandas(base_frame().assign(RatecodeID=[1, 2])))
    assert compare_aggregates(pandas_eda["code_distribution"], polars_eda["code_distribution"])[0]


def test_comparison_failure_reason_is_written_to_report(tmp_path: Path) -> None:
    (
        pandas_eda,
        polars_eda,
        pandas_cleaned,
        polars_cleaned,
        pandas_metrics,
        polars_metrics,
    ) = paired_results(base_frame())
    polars_cleaned = polars_cleaned.with_columns(
        (pl.col("fare_amount") + 1).alias("fare_amount")
    )
    pandas_quality = cleaned_quality_pandas(pandas_cleaned)
    polars_quality = cleaned_quality_polars(polars_cleaned)
    result = compare_results(
        pandas_eda, polars_eda, pandas_metrics, polars_metrics,
        pandas_quality, polars_quality,
    )
    report = tmp_path / "report.md"
    write_report(
        report, Path("sample.csv"), pd.DataFrame({"Pandas": [2], "Polars": [2]}, index=["rows"]),
        pandas_eda, polars_eda, pandas_quality, pandas_metrics, polars_metrics,
        pd.DataFrame({"Pandas": [0.1, 0.1], "Polars": [0.1, 0.1]}, index=["eda_seconds", "clean_seconds"]),
        result, inspect_date_range(pandas_cleaned["tpep_pickup_datetime"], Path("sample.csv")),
        pd.DataFrame({"Pandas": [0, 0], "Polars": [0, 0]}, index=["tpep_pickup_datetime", "tpep_dropoff_datetime"]),
    )

    text = report.read_text(encoding="utf-8")
    assert "차이 항목과 실제 비교 실패 이유" in text
    assert "정제 결과 표본·파생 변수" in text
    assert result["details"]["정제 결과 표본·파생 변수"]["reason"] in text


def test_all_original_columns_are_preserved_for_followup_analysis() -> None:
    frame = base_frame().assign(tip_amount=[1.0, 2.0], tolls_amount=[0.0, 3.0], Airport_fee=[0.0, 1.75])
    pandas_cleaned, _ = clean_data(frame, Path("sample.csv"))
    polars_cleaned, _ = clean_polars_data(pl.from_pandas(frame), Path("sample.csv"))

    assert set(frame.columns) <= set(pandas_cleaned.columns)
    assert set(frame.columns) <= set(polars_cleaned.columns)


@pytest.mark.parametrize("library", ["Pandas", "Polars"])
def test_empty_cleaned_result_is_rejected(library: str) -> None:
    pandas_cleaned, _ = clean_data(base_frame().assign(trip_distance=0), Path("sample.csv"))
    frame = pandas_cleaned if library == "Pandas" else pl.from_pandas(pandas_cleaned)

    with pytest.raises(ValueError, match=f"{library} 정제 결과가 비어"):
        validate_analysis_groups(frame, library)


@pytest.mark.parametrize("library", ["Pandas", "Polars"])
def test_empty_weekday_rush_group_is_rejected(library: str) -> None:
    frame = rush_boundary_frame().assign(
        tpep_pickup_datetime=pd.Timestamp("2025-01-06 12:00"),
        tpep_dropoff_datetime=pd.Timestamp("2025-01-06 12:30"),
    )
    pandas_cleaned, _ = clean_data(frame, Path("sample.csv"))
    cleaned = pandas_cleaned if library == "Pandas" else pl.from_pandas(pandas_cleaned)

    with pytest.raises(ValueError, match="weekday_rush"):
        validate_analysis_groups(cleaned, library)


@pytest.mark.parametrize("library", ["Pandas", "Polars"])
def test_empty_weekday_non_rush_group_is_rejected(library: str) -> None:
    pandas_cleaned, _ = clean_data(base_frame(), Path("sample.csv"))
    cleaned = pandas_cleaned if library == "Pandas" else pl.from_pandas(pandas_cleaned)

    with pytest.raises(ValueError, match="weekday_non_rush"):
        validate_analysis_groups(cleaned, library)


def test_normal_comparison_groups_pass_for_both_libraries() -> None:
    frame = rush_boundary_frame()
    pandas_cleaned, _ = clean_data(frame, Path("sample.csv"))
    polars_cleaned, _ = clean_polars_data(pl.from_pandas(frame), Path("sample.csv"))

    validate_analysis_groups(pandas_cleaned, "Pandas")
    validate_analysis_groups(polars_cleaned, "Polars")


def test_candidate_counts_match_and_specific_difference_is_reported() -> None:
    results = paired_results(rush_boundary_frame())
    pandas_quality = cleaned_quality_pandas(results[2])
    polars_quality = cleaned_quality_polars(results[3])
    matched = compare_results(
        results[0], results[1], results[4], results[5], pandas_quality, polars_quality,
    )
    assert matched["checks"]["이상치 후보 집계"] is True
    assert matched["checks"]["분석 기간 플래그 집계"] is True
    assert pandas_quality["candidate_counts"].index.tolist() == CANDIDATE_COLUMNS
    assert polars_quality["candidate_counts"].index.tolist() == CANDIDATE_COLUMNS

    polars_quality["candidate_counts"].loc["is_large_fare_candidate", "rows"] += 1
    different = compare_results(
        results[0], results[1], results[4], results[5], pandas_quality, polars_quality,
    )

    assert different["checks"]["이상치 후보 집계"] is False
    reason = different["details"]["이상치 후보 집계"]["reason"]
    assert "is_large_fare_candidate" in reason
    assert "Pandas" in reason and "Polars" in reason


def test_main_returns_zero_only_when_all_comparisons_match(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    source = tmp_path / "rush.csv"
    output = tmp_path / "cleaned.parquet"
    report = tmp_path / "report.md"
    rush_boundary_frame().to_csv(source, index=False)
    monkeypatch.setattr("sys.argv", ["prepare_data.py", str(source), "--output", str(output), "--report", str(report)])

    assert main() == 0
    assert output.is_file()
    assert not Path(f"{output}.previous").exists()
    assert "표본이 일치합니다" in report.read_text(encoding="utf-8")


def test_main_writes_mismatch_report_returns_one_and_does_not_finalize_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    source = tmp_path / "rush.csv"
    output = tmp_path / "cleaned.parquet"
    report = tmp_path / "report.md"
    rush_boundary_frame().to_csv(source, index=False)
    original_compare = prepare_data.compare_results

    def mismatching_compare(*args, **kwargs):
        result = original_compare(*args, **kwargs)
        result["matched"] = False
        result["checks"]["이상치 후보 집계"] = False
        result["details"]["이상치 후보 집계"] = {
            "matched": False,
            "reason": "후보별 불일치: {'is_large_fare_candidate': {'Pandas': 0, 'Polars': 1}}",
        }
        result["differences"] = ["이상치 후보 집계"]
        return result

    monkeypatch.setattr(prepare_data, "compare_results", mismatching_compare)
    monkeypatch.setattr("sys.argv", ["prepare_data.py", str(source), "--output", str(output), "--report", str(report)])

    assert main() == 1
    text = report.read_text(encoding="utf-8")
    assert "표본 일치 여부: **불일치**" in text
    assert "is_large_fare_candidate" in text
    assert not output.exists()
    assert not Path(f"{output}.unverified").exists()


@pytest.mark.parametrize(
    "stage",
    [
        "validate_polars_signature",
        "make_polars_eda",
        "clean_polars_data",
        "validate_analysis_groups",
        "compare_results",
        "write_report",
        "replace",
    ],
)
def test_main_cleans_unverified_file_for_every_failure_stage_and_preserves_other_files(
    stage: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    source = tmp_path / "rush.csv"
    output = tmp_path / "cleaned.parquet"
    report = tmp_path / "report.md"
    unrelated = tmp_path / "keep.txt"
    rush_boundary_frame().to_csv(source, index=False)
    output.write_bytes(b"previous-validated-result")
    report.write_text("previous-quality-report", encoding="utf-8")
    unrelated.write_text("keep", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["prepare_data.py", str(source), "--output", str(output), "--report", str(report)])

    if stage == "validate_analysis_groups":
        original = prepare_data.validate_analysis_groups

        def fail_polars_groups(frame, library):
            if library == "Polars":
                raise RuntimeError("injected group validation failure")
            return original(frame, library)

        monkeypatch.setattr(prepare_data, stage, fail_polars_groups)
    elif stage == "replace":
        original_replace = Path.replace

        def fail_temporary_replace(path, target):
            if str(path).endswith(".unverified"):
                raise RuntimeError("injected replace failure")
            return original_replace(path, target)

        monkeypatch.setattr(Path, "replace", fail_temporary_replace)
    else:
        def fail_stage(*args, **kwargs):
            raise RuntimeError(f"injected {stage} failure")

        monkeypatch.setattr(prepare_data, stage, fail_stage)

    with pytest.raises(RuntimeError, match="injected"):
        main()

    assert not Path(f"{output}.unverified").exists()
    assert not Path(f"{output}.previous").exists()
    assert output.read_bytes() == b"previous-validated-result"
    assert report.read_text(encoding="utf-8") == "previous-quality-report"
    assert unrelated.read_text(encoding="utf-8") == "keep"


def test_cleanup_is_safe_when_temporary_file_is_absent(tmp_path: Path) -> None:
    missing = tmp_path / "missing.parquet.unverified"

    prepare_data.cleanup_temporary_output(missing)

    assert not missing.exists()


def test_outlier_followup_guidance_is_in_readme_and_generated_report(tmp_path: Path) -> None:
    frame = rush_boundary_frame()
    pandas_eda = make_eda(frame)
    polars_eda = make_polars_eda(pl.from_pandas(frame))

    def render_report(
        source_name: str,
    ) -> tuple[str, pd.DataFrame, pl.DataFrame]:
        source = Path(source_name)
        report = tmp_path / f"{source.stem}.md"
        pandas_cleaned, pandas_metrics = clean_data(frame, source)
        polars_cleaned, polars_metrics = clean_polars_data(
            pl.from_pandas(frame), source
        )
        pandas_quality = cleaned_quality_pandas(pandas_cleaned)
        polars_quality = cleaned_quality_polars(polars_cleaned)
        result = compare_results(
            pandas_eda,
            polars_eda,
            pandas_metrics,
            polars_metrics,
            pandas_quality,
            polars_quality,
        )
        write_report(
            report,
            source,
            pd.DataFrame({"Pandas": [10], "Polars": [10]}, index=["rows"]),
            pandas_eda,
            polars_eda,
            pandas_quality,
            pandas_metrics,
            polars_metrics,
            pd.DataFrame(
                {"Pandas": [0.1, 0.1], "Polars": [0.1, 0.1]},
                index=["eda_seconds", "clean_seconds"],
            ),
            result,
            inspect_date_range(pandas_cleaned["tpep_pickup_datetime"], source),
            pd.DataFrame(
                {"Pandas": [0, 0], "Polars": [0, 0]},
                index=["tpep_pickup_datetime", "tpep_dropoff_datetime"],
            ),
        )
        return report.read_text(encoding="utf-8"), pandas_cleaned, polars_cleaned

    generated_without_month, pandas_without_month, polars_without_month = render_report(
        "sample.csv"
    )
    generated_with_month, _, _ = render_report("yellow_tripdata_2025-02.csv")
    expected = [
        "이상치 후보 플래그는 데이터 오류를 확정한 값이 아니며",
        "이번 전처리 단계에서는 후보 행을 임의로 제거하지",
        "이상치 후보를 포함한 결과와 제외한 결과를 함께 확인",
        "이상치 처리 기준과 결과의 민감성을 함께 보고",
        "관측 데이터이므로",
        "포함·제외 결과를 비교",
        "중앙값과 사분위수",
        "이동거리 차이",
    ]
    readme = Path("README.md").read_text(encoding="utf-8")

    assert all(text in readme for text in expected)
    assert all(text in generated_with_month for text in expected)
    assert "is_outside_source_month == False" in readme
    assert "is_outside_source_month == False" in generated_with_month
    assert "2025-02" in generated_with_month
    assert "기준 연월 밖 10행" in generated_with_month
    assert "기준 연월을 추출하지 못해" in generated_without_month
    assert "실제 승차 시각을 기준으로 별도 지정" in generated_without_month
    assert "판정하지 않음" in generated_without_month
    assert "is_outside_source_month == False" not in generated_without_month
    assert SOURCE_MONTH_FLAG not in pandas_without_month.columns
    assert SOURCE_MONTH_FLAG not in polars_without_month.columns
    original_eda_comparison = generated_with_month.split(
        "## Pandas와 Polars의 원본 EDA 결과 비교", 1,
    )[1].split("## 분석 기간 점검", 1)[0]
    final_validation = generated_with_month.split(
        "## 검증 항목 및 정제 결과 표본 일치 여부", 1,
    )[1].split("## 후속 분석 시 해석 주의사항", 1)[0]
    candidate_section = generated_with_month.split(
        "## 보존된 이상치 후보", 1,
    )[1].split("## 정제 및 EDA 실행 시간 비교", 1)[0]
    cleaned_checks = ["출퇴근 분류 분포", "평일 출퇴근·비출퇴근 통계", "이상치 후보 집계"]
    assert all(name not in original_eda_comparison for name in cleaned_checks)
    assert all(name in final_validation for name in cleaned_checks)
    assert all(generated_with_month.count(name) == 1 for name in cleaned_checks)
    assert SOURCE_MONTH_FLAG not in candidate_section
    assert "분석 기간 플래그 집계" in final_validation
