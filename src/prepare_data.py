# 작성자: 최지윤
# 작성 목적: [종합실습 2] NYC Yellow Taxi 데이터를 Pandas·Polars로 독립 정제·EDA하고 결과를 비교
# 작성일: 2026-08-07
#
# 변경사항 내역
# 2026-08-08:
# - Pandas·Polars의 독립적인 순차 로딩·EDA·정제와 정규화된 품질 결과 교차 검증을 구현
# - 출퇴근 분류값을 명시하고 품질 요약 컬럼의 역할을 분명히 하며 파생 변수·품질 플래그를 추가
# - 대용량 객체 해제, 검증 전 임시 저장과 실패 복구, 최종 확정 후 품질 보고서 생성을 반영
# 2026-08-09:
# - 기본 입력 경로를 공통 상수로 교체하고 명시적 경로 입력 기능을 유지

from __future__ import annotations

import argparse
import gc
import random
import re
import sys
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd
import polars as pl

try:
    from src.project_paths import DEFAULT_RAW_DATA
except ModuleNotFoundError:  # 직접 스크립트로 실행할 때
    from project_paths import DEFAULT_RAW_DATA

REQUIRED_COLUMNS = {
    "tpep_pickup_datetime", "tpep_dropoff_datetime", "trip_distance", "fare_amount"
}
LOAD_SAMPLE_COLUMNS = REQUIRED_COLUMNS | {
    "total_amount", "extra", "RatecodeID", "PULocationID", "DOLocationID",
    "VendorID", "passenger_count",
}
CODE_COLUMNS = ["VendorID", "RatecodeID", "PULocationID", "DOLocationID"]
NUMERIC_COLUMNS = ["trip_distance", "fare_amount", "total_amount", "extra", "passenger_count"]
LONG_TRIP_MINUTES = 24 * 60
LARGE_DISTANCE_MILES = 200
LARGE_FARE_DOLLARS = 1_000
MAX_PASSENGERS = 8
DATETIME_COLUMNS = ["tpep_pickup_datetime", "tpep_dropoff_datetime"]
SAMPLE_SIZE = 5
SAMPLE_SEED = 42
TOP_CATEGORY_VALUES = 20
DEFAULT_INPUT = DEFAULT_RAW_DATA
STAT_COLUMNS = ["count", "mean", "std", "min", "25%", "50%", "75%", "max"]
NORMALIZED_NUMERIC_COLUMNS = set(NUMERIC_COLUMNS + CODE_COLUMNS) | {
    "trip_duration_min", "pickup_hour", "fare_per_mile", "average_speed_mph",
}
MORNING_RUSH_START = 6
MORNING_RUSH_END = 10
EVENING_RUSH_START = 16
EVENING_RUSH_END = 20
RUSH_PERIODS = ["morning_rush", "evening_rush", "weekday_non_rush", "weekend"]
WEEKDAY_COMPARISON_GROUPS = ["weekday_rush", "weekday_non_rush"]
QUALITY_SUMMARY_COLUMNS = [
    "trip_duration_min", "fare_amount", "trip_distance", "fare_per_mile",
    "average_speed_mph",
]
DERIVED_VARIABLES = {
    "trip_duration_min": "하차 시각 - 승차 시각(분)",
    "pickup_hour": "승차 시각의 시(0~23)",
    "day_of_week": "승차 요일명",
    "is_weekday": "월요일~금요일 여부",
    "is_rush_hour": (
        f"평일 {MORNING_RUSH_START:02d}:00 이상 "
        f"{MORNING_RUSH_END:02d}:00 미만 또는 "
        f"{EVENING_RUSH_START:02d}:00 이상 "
        f"{EVENING_RUSH_END:02d}:00 미만 여부"
    ),
    "rush_period": "morning_rush/evening_rush/weekday_non_rush/weekend 분류",
    "weekday_comparison_group": "weekday_rush 또는 weekday_non_rush; 주말은 결측",
    "fare_per_mile": "fare_amount / trip_distance",
    "average_speed_mph": "trip_distance / (trip_duration_min / 60)",
}
CANDIDATE_COLUMNS = [
    "is_long_trip_candidate",
    "is_large_distance_candidate",
    "is_large_fare_candidate",
    "is_invalid_passenger_candidate",
]
SOURCE_MONTH_FLAG = "is_outside_source_month"
EDA_CHECKS = [
    "원본 행·열 수", "컬럼별 결측치", "날짜 범위", "범주·코드 고유값",
    "범주형 전체 빈도", "코드 전체 빈도", "주요 수치 통계", "완전 중복 행",
]


def pl_missing_expr(frame: pl.DataFrame, column: str) -> pl.Expr:
    """Polars의 null과 부동소수점 NaN을 Pandas isna와 같은 결측으로 본다."""
    expr = pl.col(column).is_null()
    return expr | pl.col(column).is_nan() if frame.schema[column].is_float() else expr


def load_one(path: Path, library: str) -> tuple[pd.DataFrame | pl.DataFrame, dict[str, float], dict[str, int]]:
    readers = {
        "Pandas": {".parquet": pd.read_parquet, ".csv": pd.read_csv, ".gz": pd.read_csv},
        "Polars": {".parquet": pl.read_parquet, ".csv": pl.read_csv, ".gz": pl.read_csv},
    }
    try:
        reader = readers[library][path.suffix.lower()]
    except KeyError as exc:
        raise ValueError("지원 형식은 .parquet, .csv, .csv.gz입니다.") from exc
    started = perf_counter()
    frame = reader(path)
    seconds = perf_counter() - started
    parse_failures: dict[str, int] = {}
    for column in DATETIME_COLUMNS:
        if column not in frame:
            continue
        if library == "Pandas":
            before = frame[column].isna()
            converted = pd.to_datetime(frame[column], errors="coerce")
            parse_failures[column] = int((converted.isna() & ~before).sum())
            frame[column] = converted
        elif frame.schema[column] == pl.String:
            before = frame[column].is_null()
            converted = frame[column].str.to_datetime(strict=False)
            parse_failures[column] = int((converted.is_null() & ~before).sum())
            frame = frame.with_columns(converted.alias(column))
        else:
            parse_failures[column] = 0
    memory_mb = (frame.memory_usage(index=True, deep=True).sum() / 1024**2
                 if library == "Pandas" else frame.estimated_size("mb"))
    metrics = {
        "load_seconds": seconds,
        "rows": len(frame),
        "columns": len(frame.columns),
        "memory_mb": memory_mb,
    }
    return frame, metrics, parse_failures


def sample_indices(row_count: int) -> list[int]:
    if row_count == 0:
        return []
    edge = min(SAMPLE_SIZE, row_count)
    indices = set(range(edge)) | set(range(max(0, row_count - edge), row_count))
    indices.update(random.Random(SAMPLE_SEED).sample(range(row_count), min(SAMPLE_SIZE, row_count)))
    return sorted(indices)


def normalize_sample(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.reset_index(drop=True).copy()
    for column in normalized:
        if column in DATETIME_COLUMNS:
            normalized[column] = pd.to_datetime(normalized[column], errors="coerce")
        elif column in NORMALIZED_NUMERIC_COLUMNS or pd.api.types.is_numeric_dtype(normalized[column]):
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
        else:
            normalized[column] = normalized[column].astype("string")
    return normalized


def compare_rows(left: pd.DataFrame, right: pd.DataFrame) -> tuple[bool, str]:
    """정제 행은 원본 인덱스만 무시하고 컬럼 순서와 값을 비교한다."""
    try:
        pd.testing.assert_frame_equal(
            normalize_sample(left), normalize_sample(right), check_dtype=False,
            check_exact=False, rtol=1e-9, atol=1e-9,
        )
        return True, ""
    except AssertionError as exc:
        return False, str(exc).replace("\n", " ")[:500]


def compare_aggregates(left: pd.DataFrame, right: pd.DataFrame) -> tuple[bool, str]:
    """EDA 집계는 dtype 표기만 허용하고 인덱스·컬럼 이름과 값은 함께 비교한다."""
    try:
        pd.testing.assert_frame_equal(
            left.sort_index(), right.sort_index(), check_dtype=False,
            check_exact=False, rtol=1e-9, atol=1e-9,
        )
        return True, ""
    except AssertionError as exc:
        return False, str(exc).replace("\n", " ")[:500]


def normalize_code_value(value: object) -> str:
    if pd.isna(value):
        return "<missing>"
    try:
        number = float(value)
        return str(int(number)) if number.is_integer() else format(number, ".15g")
    except (TypeError, ValueError):
        return str(value)


def missing_counts_polars(frame: pl.DataFrame) -> dict[str, int]:
    return {column: int(frame.select(pl_missing_expr(frame, column).sum()).item()) for column in frame.columns}


def polars_first_distinct(frame: pl.DataFrame) -> pl.Series:
    return frame.select(pl.struct(pl.all()).is_first_distinct().alias("first")).to_series()


def pandas_load_signature(frame: pd.DataFrame) -> dict[str, object]:
    indices = sample_indices(len(frame))
    columns = [column for column in frame.columns if column in LOAD_SAMPLE_COLUMNS]
    return {
        "shape": frame.shape, "columns": list(frame.columns),
        "missing": frame.isna().sum().to_dict(), "indices": indices,
        "sample_columns": columns, "sample": frame.iloc[indices][columns].copy(),
    }


def validate_polars_signature(signature: dict[str, object], frame: pl.DataFrame) -> dict[str, object]:
    if signature["shape"] != frame.shape or signature["columns"] != frame.columns:
        raise AssertionError("Pandas와 Polars의 원본 행·열 또는 컬럼 순서가 다릅니다.")
    if signature["missing"] != missing_counts_polars(frame):
        raise AssertionError("Pandas와 Polars의 컬럼별 결측치 수가 다릅니다.")
    matched, reason = compare_rows(
        signature["sample"], frame[signature["indices"]].select(signature["sample_columns"]).to_pandas()
    )
    if not matched:
        raise AssertionError(f"Pandas와 Polars의 원본 주요 컬럼 표본이 다릅니다: {reason}")
    return {"indices": signature["indices"], "columns": signature["sample_columns"], "matched": True}


def expected_month(path: Path) -> pd.Period | None:
    match = re.search(r"(20\d{2})[-_](0[1-9]|1[0-2])", path.name)
    return pd.Period(f"{match.group(1)}-{match.group(2)}", freq="M") if match else None


def inspect_date_range(pickup: pd.Series, source_path: Path) -> dict[str, object]:
    valid = pd.to_datetime(pickup, errors="coerce").dropna()
    counts = valid.dt.to_period("M").value_counts().sort_index()
    month = expected_month(source_path)
    return {
        "source_month": str(month) if month else None,
        "actual_month_count": len(counts),
        "has_multiple_months": len(counts) > 1,
        "actual_month_distribution": counts,
        "outside_source_month_rows": int(valid.dt.to_period("M").ne(month).sum()) if month else None,
    }


def summarize_categories(raw_df: pd.DataFrame) -> pd.DataFrame:
    categorical = [
        column
        for column in raw_df.select_dtypes(include=["object", "string", "category"])
        if column not in NORMALIZED_NUMERIC_COLUMNS | set(DATETIME_COLUMNS)
    ]
    summaries = []
    for column in categorical:
        counts = raw_df[column].value_counts(dropna=False)
        summary = counts.rename("count").to_frame()
        summary["ratio_pct"] = summary["count"].div(len(raw_df)).mul(100)
        summary.index = summary.index.map(lambda value: "<missing>" if pd.isna(value) else str(value))
        summaries.append(pd.concat({column: summary}, names=["column", "value"]))
    return pd.concat(summaries) if summaries else pd.DataFrame(
        columns=["count", "ratio_pct"]
    )


def _pandas_distribution(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    parts = {}
    for column in columns:
        normalized = frame[column].map(normalize_code_value)
        counts = normalized.value_counts(dropna=False).sort_index()
        parts[column] = counts
    if not parts:
        return pd.DataFrame(columns=["count"])
    return pd.concat(parts, names=["column", "value"]).rename("count").to_frame()


def make_eda(raw_df: pd.DataFrame) -> dict[str, object]:
    rows = len(raw_df)
    missing = raw_df.isna().sum().rename("missing_count").to_frame()
    missing["missing_ratio_pct"] = missing["missing_count"].div(rows).mul(100) if rows else 0.0
    numeric = [column for column in NUMERIC_COLUMNS if column in raw_df]
    codes = [column for column in CODE_COLUMNS if column in raw_df]
    dates = [column for column in DATETIME_COLUMNS if column in raw_df]
    categories = [
        column
        for column in raw_df.select_dtypes(include=["object", "string", "category"])
        if column not in NORMALIZED_NUMERIC_COLUMNS | set(DATETIME_COLUMNS)
    ]
    category_unique = pd.Series(
        {column: raw_df[column].nunique(dropna=False) for column in categories},
        name="unique_count",
        dtype="int64",
    ).to_frame()
    code_unique = pd.Series(
        {column: raw_df[column].nunique(dropna=False) for column in codes},
        name="unique_count",
    ).to_frame()
    return {
        "shape": raw_df.shape,
        "schema": pd.DataFrame({"dtype": raw_df.dtypes.astype(str)}),
        "missing": missing,
        "duplicate_rows": int(raw_df.duplicated().sum()),
        "numeric_summary": raw_df[numeric].apply(pd.to_numeric, errors="coerce").describe(percentiles=[.25, .5, .75]).T,
        "datetime_range": pd.DataFrame({"min": raw_df[dates].min(), "max": raw_df[dates].max()}),
        "category_distribution": summarize_categories(raw_df),
        "category_unique": category_unique,
        "code_distribution": _pandas_distribution(raw_df, codes),
        "code_unique": code_unique,
    }


def _polars_distribution(frame: pl.DataFrame, columns: list[str]) -> pd.DataFrame:
    records = []
    for column in columns:
        normalized = (
            pl.when(pl_missing_expr(frame, column))
            .then(pl.lit("<missing>"))
            .otherwise(pl.col(column).cast(pl.String))
            .alias("value")
        )
        counts = frame.select(normalized).group_by("value").len().sort("value")
        records.extend((column, normalize_code_value(value), count) for value, count in counts.iter_rows())
    if not records:
        return pd.DataFrame(columns=["count"])
    return pd.DataFrame(records, columns=["column", "value", "count"]).set_index(["column", "value"])


def make_polars_eda(raw_df: pl.DataFrame) -> dict[str, object]:
    """변환 없이 Polars API로 원본 EDA를 계산하고 작은 집계만 Pandas로 반환한다."""
    rows = raw_df.height
    missing_map = missing_counts_polars(raw_df)
    missing = pd.DataFrame({"missing_count": missing_map})
    missing["missing_ratio_pct"] = missing["missing_count"].div(rows).mul(100) if rows else 0.0
    numeric = [column for column in NUMERIC_COLUMNS if column in raw_df]
    codes = [column for column in CODE_COLUMNS if column in raw_df]
    categories = [column for column, dtype in raw_df.schema.items() if dtype == pl.String or dtype == pl.Categorical]
    stats = {}
    for column in numeric:
        series = raw_df[column].drop_nans().drop_nulls()
        stats[column] = [series.len(), series.mean(), series.std(), series.min(),
                         series.quantile(.25, interpolation="linear"),
                         series.quantile(.5, interpolation="linear"),
                         series.quantile(.75, interpolation="linear"), series.max()]
    date_records = {}
    for column in DATETIME_COLUMNS:
        if column in raw_df:
            date_records[column] = {"min": raw_df[column].min(), "max": raw_df[column].max()}
    category_distribution = _polars_distribution(raw_df, categories)
    if not category_distribution.empty:
        category_distribution["ratio_pct"] = category_distribution["count"].div(rows).mul(100)
    category_unique = pd.DataFrame({
        "unique_count": {
            column: raw_df.select(
                pl.when(pl_missing_expr(raw_df, column))
                .then(pl.lit("<missing>"))
                .otherwise(pl.col(column))
                .n_unique()
            ).item()
            for column in categories
        }
    })
    code_unique = pd.DataFrame({
        "unique_count": {
            column: raw_df.select(
                pl.when(pl_missing_expr(raw_df, column))
                .then(pl.lit("<missing>"))
                .otherwise(pl.col(column).cast(pl.String))
                .n_unique()
            ).item()
            for column in codes
        }
    })
    return {
        "shape": raw_df.shape,
        "schema": pd.DataFrame({"dtype": [str(dtype) for dtype in raw_df.dtypes]}, index=raw_df.columns),
        "missing": missing,
        "duplicate_rows": int((~polars_first_distinct(raw_df)).sum()),
        "numeric_summary": pd.DataFrame.from_dict(stats, orient="index", columns=STAT_COLUMNS),
        "datetime_range": pd.DataFrame.from_dict(date_records, orient="index"),
        "category_distribution": category_distribution,
        "category_unique": category_unique,
        "code_distribution": _polars_distribution(raw_df, codes),
        "code_unique": code_unique,
    }


def clean_data(raw_df: pd.DataFrame, source_path: Path) -> tuple[pd.DataFrame, dict[str, int]]:
    """분석 불가능한 중복·결측·시각 및 0 이하 값을 제거한다.

    극단값은 삭제하지 않고 이상치 후보 플래그로 보존한다.
    """
    missing_columns = sorted(REQUIRED_COLUMNS - set(raw_df.columns))
    if missing_columns:
        raise ValueError(f"필수 컬럼이 없습니다: {', '.join(missing_columns)}")
    cleaned = raw_df.drop_duplicates().copy()
    core_missing = cleaned[list(REQUIRED_COLUMNS)].isna().any(axis=1)
    cleaned = cleaned.loc[~core_missing].copy()
    for column in DATETIME_COLUMNS:
        cleaned[column] = pd.to_datetime(cleaned[column], errors="coerce")
    pickup, dropoff = cleaned[DATETIME_COLUMNS[0]], cleaned[DATETIME_COLUMNS[1]]
    invalid_datetime = pickup.isna() | dropoff.isna()
    cleaned = cleaned.loc[~invalid_datetime].copy()
    pickup, dropoff = cleaned[DATETIME_COLUMNS[0]], cleaned[DATETIME_COLUMNS[1]]
    duration = (dropoff - pickup).dt.total_seconds().div(60)
    invalid_duration = duration.le(0)
    invalid_distance = cleaned["trip_distance"].le(0)
    invalid_fare = cleaned["fare_amount"].le(0)
    invalid = invalid_duration | invalid_distance | invalid_fare
    cleaned, duration, pickup = cleaned.loc[~invalid].copy(), duration.loc[~invalid], pickup.loc[~invalid]
    cleaned["trip_duration_min"] = duration
    cleaned["pickup_hour"] = pickup.dt.hour.astype("int8")
    cleaned["day_of_week"] = pickup.dt.day_name()
    cleaned["is_weekday"] = pickup.dt.dayofweek.lt(5)
    morning = cleaned["is_weekday"] & cleaned["pickup_hour"].between(
        MORNING_RUSH_START, MORNING_RUSH_END, inclusive="left"
    )
    evening = cleaned["is_weekday"] & cleaned["pickup_hour"].between(
        EVENING_RUSH_START, EVENING_RUSH_END, inclusive="left"
    )
    cleaned["is_rush_hour"] = morning | evening
    cleaned["rush_period"] = np.select(
        [morning, evening, cleaned["is_weekday"]],
        ["morning_rush", "evening_rush", "weekday_non_rush"],
        default="weekend",
    )
    cleaned["weekday_comparison_group"] = pd.Series(
        np.where(cleaned["is_weekday"], np.where(cleaned["is_rush_hour"], "weekday_rush", "weekday_non_rush"), None),
        index=cleaned.index, dtype="string",
    )
    cleaned["fare_per_mile"] = cleaned["fare_amount"] / cleaned["trip_distance"]
    cleaned["average_speed_mph"] = cleaned["trip_distance"] / (duration / 60)
    cleaned["is_long_trip_candidate"] = duration.gt(LONG_TRIP_MINUTES)
    cleaned["is_large_distance_candidate"] = cleaned["trip_distance"].gt(LARGE_DISTANCE_MILES)
    cleaned["is_large_fare_candidate"] = cleaned["fare_amount"].gt(LARGE_FARE_DOLLARS)
    if "passenger_count" in cleaned:
        invalid_passenger = (
            cleaned["passenger_count"].le(0)
            | cleaned["passenger_count"].gt(MAX_PASSENGERS)
        )
        cleaned["is_invalid_passenger_candidate"] = invalid_passenger.fillna(False)
    month = expected_month(source_path)
    if month:
        cleaned[SOURCE_MONTH_FLAG] = ~pickup.between(
            month.start_time,
            (month + 1).start_time,
            inclusive="left",
        )
    metrics = {
        "raw_rows": len(raw_df), "duplicate_rows_removed": int(raw_df.duplicated().sum()),
        "core_missing_rows_removed": int(core_missing.sum()),
        "invalid_datetime_rows_removed": int(invalid_datetime.sum()),
        "nonpositive_duration_rows": int(invalid_duration.sum()),
        "nonpositive_distance_rows": int(invalid_distance.sum()),
        "nonpositive_fare_rows": int(invalid_fare.sum()),
        "nonpositive_duration_distance_or_fare_removed": int(invalid.sum()),
        "cleaned_rows": len(cleaned),
    }
    return cleaned, metrics


def clean_polars_data(raw_df: pl.DataFrame, source_path: Path) -> tuple[pl.DataFrame, dict[str, int]]:
    """분석 불가능한 중복·결측·시각 및 0 이하 값을 제거한다.

    극단값은 삭제하지 않고 이상치 후보 플래그로 보존한다.
    """
    missing_columns = sorted(REQUIRED_COLUMNS - set(raw_df.columns))
    if missing_columns:
        raise ValueError(f"필수 컬럼이 없습니다: {', '.join(missing_columns)}")
    first_distinct = polars_first_distinct(raw_df)
    duplicate_count = int((~first_distinct).sum())
    cleaned = raw_df.filter(first_distinct)
    core_expr = pl.any_horizontal([pl_missing_expr(cleaned, column) for column in REQUIRED_COLUMNS])
    core_count = cleaned.select(core_expr.sum()).item()
    cleaned = cleaned.filter(~core_expr)
    casts = []
    for column in DATETIME_COLUMNS:
        expression = (
            pl.col(column)
            if cleaned.schema[column].is_temporal()
            else pl.col(column).cast(pl.String).str.to_datetime(strict=False)
        )
        casts.append(expression)
    cleaned = cleaned.with_columns(casts)
    invalid_datetime_expr = pl.any_horizontal([pl.col(column).is_null() for column in DATETIME_COLUMNS])
    invalid_datetime_count = cleaned.select(invalid_datetime_expr.sum()).item()
    cleaned = cleaned.filter(~invalid_datetime_expr)
    duration = (pl.col(DATETIME_COLUMNS[1]) - pl.col(DATETIME_COLUMNS[0])).dt.total_seconds() / 60
    invalid_duration = duration <= 0
    invalid_distance = pl.col("trip_distance") <= 0
    invalid_fare = pl.col("fare_amount") <= 0
    invalid = invalid_duration | invalid_distance | invalid_fare
    counts = cleaned.select(
        invalid_duration.sum().alias("duration"), invalid_distance.sum().alias("distance"),
        invalid_fare.sum().alias("fare"), invalid.sum().alias("any"),
    ).row(0, named=True)
    cleaned = cleaned.filter(~invalid).with_columns(
        duration.alias("trip_duration_min"),
        pl.col(DATETIME_COLUMNS[0]).dt.hour().cast(pl.Int8).alias("pickup_hour"),
        pl.col(DATETIME_COLUMNS[0]).dt.strftime("%A").alias("day_of_week"),
        (pl.col(DATETIME_COLUMNS[0]).dt.weekday() <= 5).alias("is_weekday"),
    )
    weekday = pl.col("is_weekday")
    hour = pl.col("pickup_hour")
    morning = weekday & hour.is_between(MORNING_RUSH_START, MORNING_RUSH_END, closed="left")
    evening = weekday & hour.is_between(EVENING_RUSH_START, EVENING_RUSH_END, closed="left")
    cleaned = cleaned.with_columns(
        (morning | evening).alias("is_rush_hour"),
        pl.when(morning).then(pl.lit("morning_rush"))
        .when(evening).then(pl.lit("evening_rush"))
        .when(weekday).then(pl.lit("weekday_non_rush"))
        .otherwise(pl.lit("weekend")).alias("rush_period"),
        pl.when(weekday)
        .then(pl.when(morning | evening).then(pl.lit("weekday_rush")).otherwise(pl.lit("weekday_non_rush")))
        .otherwise(pl.lit(None, dtype=pl.String)).alias("weekday_comparison_group"),
        (pl.col("fare_amount") / pl.col("trip_distance")).alias("fare_per_mile"),
        (pl.col("trip_distance") / (pl.col("trip_duration_min") / 60)).alias("average_speed_mph"),
        (pl.col("trip_duration_min") > LONG_TRIP_MINUTES).alias("is_long_trip_candidate"),
        (pl.col("trip_distance") > LARGE_DISTANCE_MILES).alias("is_large_distance_candidate"),
        (pl.col("fare_amount") > LARGE_FARE_DOLLARS).alias("is_large_fare_candidate"),
    )
    if "passenger_count" in cleaned:
        invalid_passenger = (
            (pl.col("passenger_count") <= 0)
            | (pl.col("passenger_count") > MAX_PASSENGERS)
        )
        cleaned = cleaned.with_columns(
            invalid_passenger.fill_null(False).alias("is_invalid_passenger_candidate")
        )
    month = expected_month(source_path)
    if month:
        start, end = month.start_time.to_pydatetime(), (month + 1).start_time.to_pydatetime()
        outside_source_month = (
            (pl.col(DATETIME_COLUMNS[0]) < start)
            | (pl.col(DATETIME_COLUMNS[0]) >= end)
        )
        cleaned = cleaned.with_columns(
            outside_source_month.alias(SOURCE_MONTH_FLAG)
        )
    metrics = {
        "raw_rows": raw_df.height, "duplicate_rows_removed": duplicate_count,
        "core_missing_rows_removed": int(core_count),
        "invalid_datetime_rows_removed": int(invalid_datetime_count),
        "nonpositive_duration_rows": int(counts["duration"]),
        "nonpositive_distance_rows": int(counts["distance"]),
        "nonpositive_fare_rows": int(counts["fare"]),
        "nonpositive_duration_distance_or_fare_removed": int(counts["any"]),
        "cleaned_rows": cleaned.height,
    }
    return cleaned, metrics


def _stats(values: pd.Series) -> list[float]:
    return pd.to_numeric(values, errors="coerce").describe(percentiles=[.25, .5, .75]).reindex(STAT_COLUMNS).tolist()


def cleaned_quality_pandas(frame: pd.DataFrame) -> dict[str, object]:
    rush_counts = frame["rush_period"].value_counts().reindex(RUSH_PERIODS, fill_value=0)
    rush_distribution = rush_counts.rename("count").to_frame()
    rush_distribution["ratio_pct"] = rush_distribution["count"].div(len(frame)).mul(100)
    records = {
        (group, column): _stats(frame.loc[frame["weekday_comparison_group"].eq(group), column])
        for group in WEEKDAY_COMPARISON_GROUPS
        for column in QUALITY_SUMMARY_COLUMNS
    }
    rush_summary = pd.DataFrame.from_dict(records, orient="index", columns=STAT_COLUMNS)
    rush_summary.index = pd.MultiIndex.from_tuples(rush_summary.index, names=["group", "variable"])
    source_month_count = (
        int(frame[SOURCE_MONTH_FLAG].sum()) if SOURCE_MONTH_FLAG in frame else None
    )
    candidate_counts = pd.DataFrame({
        "rows": {
            column: int(frame[column].sum()) if column in frame else 0
            for column in CANDIDATE_COLUMNS
        }
    })
    return {
        "columns": list(frame.columns),
        "sample": frame.iloc[sample_indices(len(frame))].copy(),
        "rush_distribution": rush_distribution,
        "rush_summary": rush_summary,
        "candidate_counts": candidate_counts,
        "source_month_count": source_month_count,
    }


def cleaned_quality_polars(frame: pl.DataFrame) -> dict[str, object]:
    counts = dict(frame.group_by("rush_period").len().iter_rows())
    rush_distribution = pd.DataFrame(
        {"count": [counts.get(period, 0) for period in RUSH_PERIODS]},
        index=pd.Index(RUSH_PERIODS, name="rush_period"),
    )
    rush_distribution["ratio_pct"] = rush_distribution["count"].div(frame.height).mul(100)
    records = {}
    for group in WEEKDAY_COMPARISON_GROUPS:
        selected = frame.filter(pl.col("weekday_comparison_group") == group)
        for column in QUALITY_SUMMARY_COLUMNS:
            series = selected[column].drop_nans().drop_nulls()
            values = [series.len(), series.mean(), series.std(), series.min(),
                series.quantile(.25, interpolation="linear"), series.quantile(.5, interpolation="linear"),
                series.quantile(.75, interpolation="linear"), series.max()]
            records[(group, column)] = [np.nan if value is None else value for value in values]
    rush_summary = pd.DataFrame.from_dict(records, orient="index", columns=STAT_COLUMNS)
    rush_summary.index = pd.MultiIndex.from_tuples(rush_summary.index, names=["group", "variable"])
    source_month_count = (
        int(frame[SOURCE_MONTH_FLAG].sum()) if SOURCE_MONTH_FLAG in frame else None
    )
    candidate_counts = pd.DataFrame({
        "rows": {
            column: int(frame[column].sum()) if column in frame else 0
            for column in CANDIDATE_COLUMNS
        }
    })
    return {
        "columns": frame.columns,
        "sample": frame[sample_indices(frame.height)].to_pandas(),
        "rush_distribution": rush_distribution,
        "rush_summary": rush_summary,
        "candidate_counts": candidate_counts,
        "source_month_count": source_month_count,
    }


def validate_analysis_groups(frame: pd.DataFrame | pl.DataFrame, library: str) -> None:
    """정제 결과와 후속 비교에 필요한 두 평일 집단이 모두 존재하는지 검증한다."""
    row_count = len(frame)
    if row_count == 0:
        raise ValueError(f"{library} 정제 결과가 비어 있습니다. 정제 기준과 원본 데이터 품질을 확인하세요.")
    if isinstance(frame, pd.DataFrame):
        counts = frame["weekday_comparison_group"].value_counts().to_dict()
    else:
        counts = dict(frame.group_by("weekday_comparison_group").len().iter_rows())
    empty_groups = [
        group for group in WEEKDAY_COMPARISON_GROUPS if counts.get(group, 0) == 0
    ]
    if empty_groups:
        raise ValueError(f"{library} 비교 집단이 비어 있습니다: {', '.join(empty_groups)}. 후속 시각화와 통계 검정을 수행할 수 없습니다.")


def compare_results(
    pandas_eda: dict[str, object], polars_eda: dict[str, object],
    pandas_metrics: dict[str, int], polars_metrics: dict[str, int],
    pandas_quality: dict[str, object], polars_quality: dict[str, object],
) -> dict[str, object]:
    details: dict[str, dict[str, object]] = {}

    def record(name: str, matched: bool, reason: str = "") -> None:
        details[name] = {"matched": bool(matched), "reason": reason if not matched else ""}

    record(
        "원본 행·열 수",
        pandas_eda["shape"] == polars_eda["shape"],
        f"{pandas_eda['shape']} != {polars_eda['shape']}",
    )
    aggregate_checks = [
        ("컬럼별 결측치", pandas_eda["missing"], polars_eda["missing"]),
        ("날짜 범위", pandas_eda["datetime_range"], polars_eda["datetime_range"]),
        (
            "범주·코드 고유값",
            pd.concat([pandas_eda["category_unique"], pandas_eda["code_unique"]]),
            pd.concat([polars_eda["category_unique"], polars_eda["code_unique"]]),
        ),
        (
            "범주형 전체 빈도",
            pandas_eda["category_distribution"],
            polars_eda["category_distribution"],
        ),
        ("코드 전체 빈도", pandas_eda["code_distribution"], polars_eda["code_distribution"]),
        (
            "주요 수치 통계",
            pandas_eda["numeric_summary"].reindex(columns=STAT_COLUMNS),
            polars_eda["numeric_summary"],
        ),
        (
            "출퇴근 분류 분포",
            pandas_quality["rush_distribution"],
            polars_quality["rush_distribution"],
        ),
        (
            "평일 출퇴근·비출퇴근 통계",
            pandas_quality["rush_summary"],
            polars_quality["rush_summary"],
        ),
    ]
    for name, left, right in aggregate_checks:
        matched, reason = compare_aggregates(left, right)
        record(name, matched, reason)
    record(
        "완전 중복 행",
        pandas_eda["duplicate_rows"] == polars_eda["duplicate_rows"],
        f"{pandas_eda['duplicate_rows']} != {polars_eda['duplicate_rows']}",
    )
    record("단계별 제거 행 수", pandas_metrics == polars_metrics, f"Pandas={pandas_metrics}, Polars={polars_metrics}")
    candidate_left = pandas_quality["candidate_counts"]
    candidate_right = polars_quality["candidate_counts"]
    candidate_matched, _ = compare_aggregates(candidate_left, candidate_right)
    candidate_differences = {
        candidate: {
            "Pandas": int(candidate_left.loc[candidate, "rows"]),
            "Polars": int(candidate_right.loc[candidate, "rows"]),
        }
        for candidate in CANDIDATE_COLUMNS
        if int(candidate_left.loc[candidate, "rows"]) != int(candidate_right.loc[candidate, "rows"])
    }
    record("이상치 후보 집계", candidate_matched, f"후보별 불일치: {candidate_differences}")
    source_month_matched = (
        pandas_quality["source_month_count"] == polars_quality["source_month_count"]
    )
    record(
        "분석 기간 플래그 집계",
        source_month_matched,
        (
            f"Pandas={pandas_quality['source_month_count']}, "
            f"Polars={polars_quality['source_month_count']}"
        ),
    )
    columns_match = pandas_quality["columns"] == polars_quality["columns"]
    record("최종 컬럼 순서", columns_match, "최종 컬럼명 또는 순서가 다릅니다.")
    matched, reason = (
        compare_rows(pandas_quality["sample"], polars_quality["sample"])
        if columns_match
        else (False, "컬럼 불일치로 표본 비교를 생략했습니다.")
    )
    record("정제 결과 표본·파생 변수", matched, reason)
    differences = [name for name, detail in details.items() if not detail["matched"]]
    return {
        "matched": not differences,
        "checks": {name: detail["matched"] for name, detail in details.items()},
        "details": details,
        "differences": differences,
    }


def _section(title: str, tables: list[tuple[str, pd.DataFrame]]) -> list[str]:
    lines = [f"## {title}", ""]
    for name, table in tables:
        lines += [f"### {name}", "", table.to_markdown(floatfmt=".4f"), ""]
    return lines


def display_top(distribution: pd.DataFrame) -> pd.DataFrame:
    if distribution.empty:
        return distribution
    return pd.concat([
        group.sort_values(["count"], ascending=False).head(TOP_CATEGORY_VALUES)
        for _, group in distribution.groupby(level="column", sort=False)
    ])


def write_report(
    path: Path, source: Path, comparison: pd.DataFrame,
    pandas_eda: dict[str, object], polars_eda: dict[str, object],
    pandas_quality: dict[str, object], pandas_metrics: dict[str, int],
    polars_metrics: dict[str, int], timings: pd.DataFrame,
    result: dict[str, object], date_quality: dict[str, object],
    parse_failures: pd.DataFrame,
) -> None:
    check_table = pd.DataFrame({
        "일치": {
            name: "통과" if value else "불일치"
            for name, value in result["checks"].items()
        }
    })
    metric_table = pd.DataFrame({"Pandas": pandas_metrics, "Polars": polars_metrics})
    failure_lines = [
        f"- **{name}**: {detail['reason']}"
        for name, detail in result["details"].items()
        if not detail["matched"]
    ]
    derived = pd.Series(DERIVED_VARIABLES, name="정의").to_frame()
    raw_summary = pd.DataFrame(
        {
            "Pandas": [
                pandas_eda["shape"][0],
                pandas_eda["shape"][1],
                pandas_eda["duplicate_rows"],
            ],
            "Polars": [
                polars_eda["shape"][0],
                polars_eda["shape"][1],
                polars_eda["duplicate_rows"],
            ],
        },
        index=["rows", "columns", "full_duplicate_rows"],
    )
    source_month = date_quality["source_month"]
    if source_month:
        source_month_guidance = (
            f"분석 대상을 {source_month}로 한정하면 "
            "`is_outside_source_month == False`인 행을 주 분석에 사용합니다. "
            f"정제 후 확인된 기준 연월 밖 {pandas_quality['source_month_count']}행은 "
            "데이터 준비 단계에서 삭제하지 않았으며, 포함 여부는 후속 분석 목적에 따라 "
            "결정하고 필요하면 포함·제외 결과를 비교합니다."
        )
    else:
        source_month_guidance = (
            "입력 파일명에서 기준 연월을 추출하지 못해 `is_outside_source_month` 컬럼을 "
            "생성하지 않았습니다. 분석 대상 기간은 실제 승차 시각을 기준으로 별도 지정해야 합니다."
        )
    pandas_eda_tables = [
        ("dtype", pandas_eda["schema"]),
        ("결측치", pandas_eda["missing"]),
        ("주요 수치형 기초 통계", pandas_eda["numeric_summary"]),
        ("날짜 범위", pandas_eda["datetime_range"]),
        ("범주형 컬럼별 고유값 수", pandas_eda["category_unique"]),
        ("범주형 주요 값 빈도·비율", display_top(pandas_eda["category_distribution"])),
        ("코드 컬럼별 고유값 수", pandas_eda["code_unique"]),
        ("주요 코드 빈도", display_top(pandas_eda["code_distribution"])),
    ]
    polars_eda_tables = [
        ("dtype", polars_eda["schema"]),
        ("결측치", polars_eda["missing"]),
        ("주요 수치형 기초 통계", polars_eda["numeric_summary"]),
        ("날짜 범위", polars_eda["datetime_range"]),
        ("범주형 컬럼별 고유값 수", polars_eda["category_unique"]),
        ("범주형 주요 값 빈도·비율", display_top(polars_eda["category_distribution"])),
        ("코드 컬럼별 고유값 수", polars_eda["code_unique"]),
        ("주요 코드 빈도", display_top(polars_eda["code_distribution"])),
    ]
    lines = [
        "# 데이터 품질 및 전처리 결과", "", f"- 원본: `{source}`",
        f"- 크기: {pandas_eda['shape'][0]:,}행 × {pandas_eda['shape'][1]:,}열",
        f"- 검증 항목 및 정제 결과 표본 일치 여부: **{'일치' if result['matched'] else '불일치'}**",
        "- 정제 결과는 앞·뒤 각 최대 5행과 seed=42 고정 표본을 비교했습니다. 전체 행 해시 검증은 수행하지 않았습니다.", "",
        "## 로딩 시간·메모리 비교", "", comparison.to_markdown(floatfmt=".4f"), "",
        (
            "시간은 각 라이브러리 1회 측정 참고값입니다. 두 번째 실행은 OS 파일 캐시의 "
            "영향을 받을 수 있으며 단일 실행으로 항상 더 빠른 라이브러리를 단정할 수 없습니다. "
            "Pandas와 Polars의 메모리 계산 방식도 서로 달라 각 라이브러리 추정치일 뿐 "
            "동일 기준의 정밀 벤치마크가 아닙니다."
        ), "",
        "## 원본 품질 요약", "",
        raw_summary.to_markdown(), "",
        "### 날짜 파싱 실패", "", parse_failures.to_markdown(), "",
        "CSV 문자열 날짜는 로딩 시 datetime으로 변환하며, 변환 실패 수를 위 표에 별도 집계합니다. 변환된 NaT/null은 이후 핵심 결측 제거 수에도 포함됩니다.", "",
    ]
    lines += _section("Pandas EDA 결과", pandas_eda_tables)
    lines += _section("Polars EDA 결과", polars_eda_tables)
    lines += [
        "## Pandas와 Polars의 원본 EDA 결과 비교", "",
        check_table.loc[EDA_CHECKS].to_markdown(), "",
        "dtype 이름은 라이브러리 고유 표현이므로 값 일치 판정에서 제외했습니다. 수치에는 rtol/atol 1e-9를 적용하고 null/NaN과 정수/실수 표현을 정규화했습니다.", "",
        "## 분석 기간 점검", "",
        f"- 파일명 기준 연월: `{date_quality['source_month'] or '추출 불가'}`",
        f"- 실제 연월 수: {date_quality['actual_month_count']}",
        f"- 여러 연월 혼재: {date_quality['has_multiple_months']}",
        (
            f"- 정제 후 기준 연월 밖 행: {pandas_quality['source_month_count']}"
            if pandas_quality["source_month_count"] is not None
            else "- 정제 후 기준 연월 밖 행: 판정하지 않음"
        ), "",
        date_quality["actual_month_distribution"].rename("rows").to_frame().to_markdown(), "",
        source_month_guidance, "",
    ]
    lines += [
        "## Pandas와 Polars의 단계별 정제 결과 비교", "", metric_table.to_markdown(), "",
        "## 요금 지표의 의미", "",
        (
            "- `fare_amount`는 택시미터가 시간과 이동거리를 기준으로 계산한 운임이며, "
            "본 분석의 주요 요금 지표로 사용합니다."
        ),
        (
            "- `total_amount`는 승객에게 청구된 총금액이며, 현금으로 지급된 팁은 "
            "포함되지 않습니다."
        ),
        "- 아래 출퇴근 집단 비교의 `fare_amount` 통계는 미터 운임 통계입니다.", "",
        "## 생성된 파생 변수", "", derived.to_markdown(), "",
    ]
    lines += [
        "## 출퇴근 시간대 분류", "", pandas_quality["rush_distribution"].to_markdown(floatfmt=".4f"), "",
        "주 비교 집단은 `weekday_rush`와 `weekday_non_rush`이며 주말은 비교 집단에서 제외합니다.", "",
        "## 평일 출퇴근·비출퇴근 핵심 변수 기초 통계", "", pandas_quality["rush_summary"].to_markdown(floatfmt=".4f"), "",
        "이 표는 후속 시각화와 통계 검정을 위한 데이터 품질 확인이며 평균 차이만으로 결론을 내리지 않습니다.", "",
    ]
    lines += [
        "## 보존된 이상치 후보", "", pandas_quality["candidate_counts"].to_markdown(), "",
        "이상치 후보 플래그는 데이터 오류를 확정한 값이 아니며, 이번 전처리 단계에서는 후보 행을 임의로 제거하지 않았습니다.", "",
        "## 정제 및 EDA 실행 시간 비교", "", timings.to_markdown(floatfmt=".6f"), "",
        "## 검증 항목 및 정제 결과 표본 일치 여부", "", check_table.to_markdown(), "",
        f"- 결론: **{'검증 항목과 정제 결과 표본이 일치합니다.' if result['matched'] else '차이가 발견되었습니다.'}**",
        "### 차이 항목과 실제 비교 실패 이유", "", *(failure_lines or ["- 없음"]), "",
    ]
    lines += [
        "## 후속 분석 시 해석 주의사항", "",
        (
            "- 후속 시각화와 통계 검정에서는 이상치 후보를 포함한 결과와 제외한 결과를 "
            "함께 확인하여, 소수의 극단값이 이동시간과 미터 운임의 평균 차이 및 검정 "
            "결과에 미치는 영향을 점검해야 합니다. 두 분석의 결론이 달라질 경우 이상치 "
            "처리 기준과 결과의 민감성을 함께 보고해야 합니다."
        ),
        "- 이상치 후보의 포함·제외 분석은 후속 시각화와 통계 분석 단계에서 수행하며, 이 보고서에는 데이터에서 확인하지 않은 수치나 분석 결론을 작성하지 않습니다.",
        "- 이동시간과 미터 운임은 이동거리, 승·하차 지역, 요금 코드 및 기타 요금 구성의 영향을 받을 수 있습니다.",
        "- 현재 출퇴근 시간대 분류는 요일만을 기준으로 하며, 평일 공휴일을 별도로 제외하지 않았습니다. 따라서 공휴일의 이동 특성이 평일 출퇴근 집단에 일부 포함될 수 있습니다.",
        "- 평일 비출퇴근 집단에는 새벽·주간·야간이 모두 포함되므로, 후속 회귀 또는 ML 분석에서는 승차 시각, 승하차 지역, 이동거리 등의 변수를 함께 고려해야 합니다.",
        (
            "- 기존 이상치 후보를 제외해도 모든 파생 변수 극단값이 제거되는 것은 아닙니다. "
            "`fare_per_mile`과 `average_speed_mph`의 분포는 평균뿐 아니라 중앙값과 "
            "사분위수를 함께 확인해야 합니다."
        ),
        "- 현실적으로 해석하기 어려운 속도와 단위 거리당 미터 운임은 포함·제외 결과를 비교하고, 이동거리 차이를 고려하지 않은 채 출퇴근 집단의 이동시간이나 미터 운임 차이를 해석하지 않습니다.",
        "- 시각화와 t-test는 집단 간 차이를 확인하는 단계이며, 이 준비 단계에서는 수행하지 않습니다.",
        "- 관측 데이터이므로 결과는 엄밀한 인과관계가 아니라 차이 또는 연관성으로 해석해야 합니다.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def verify(raw_df: pd.DataFrame, cleaned_df: pd.DataFrame) -> None:
    assert len(cleaned_df) <= len(raw_df)
    assert not cleaned_df.duplicated().any()
    assert not cleaned_df[list(REQUIRED_COLUMNS)].isna().any().any()
    assert set(raw_df.columns) <= set(cleaned_df.columns), "원본 컬럼이 누락됐습니다."
    recalculated = (
        cleaned_df[DATETIME_COLUMNS[1]] - cleaned_df[DATETIME_COLUMNS[0]]
    ).dt.total_seconds().div(60)
    assert np.allclose(cleaned_df["trip_duration_min"], recalculated, equal_nan=True)
    assert np.allclose(
        pd.to_numeric(cleaned_df["fare_per_mile"]),
        pd.to_numeric(cleaned_df["fare_amount"] / cleaned_df["trip_distance"]),
    )
    assert np.allclose(
        pd.to_numeric(cleaned_df["average_speed_mph"]),
        pd.to_numeric(
            cleaned_df["trip_distance"] / (cleaned_df["trip_duration_min"] / 60)
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NYC Yellow Taxi 데이터 준비")
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"원본 Parquet 또는 CSV 경로 (기본값: {DEFAULT_INPUT})",
    )
    parser.add_argument("--output", type=Path, default=Path("data/processed/yellow_taxi_cleaned.parquet"))
    parser.add_argument("--report", type=Path, default=Path("reports/generated/data_quality_report.md"))
    return parser.parse_args()


def cleanup_temporary_output(path: Path) -> None:
    """기존 처리 예외를 덮어쓰지 않도록 이번 실행의 임시 파일을 최선으로 정리한다."""
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def main() -> int:
    args = parse_args()
    if not args.input.is_file():
        raise FileNotFoundError(
            f"입력 데이터 파일을 찾을 수 없습니다: {args.input}. "
            f"기본 실행에는 '{DEFAULT_INPUT}' 파일이 필요하며, "
            "다른 파일은 첫 번째 인수로 지정하세요."
        )
    pandas_raw, pandas_load, pandas_parse_failures = load_one(args.input, "Pandas")
    load_signature = pandas_load_signature(pandas_raw)
    started = perf_counter()
    pandas_eda = make_eda(pandas_raw)
    pandas_eda_seconds = perf_counter() - started
    started = perf_counter()
    pandas_cleaned, pandas_metrics = clean_data(pandas_raw, args.input)
    pandas_clean_seconds = perf_counter() - started
    date_quality = inspect_date_range(pandas_raw[DATETIME_COLUMNS[0]], args.input)
    verify(pandas_raw, pandas_cleaned)
    validate_analysis_groups(pandas_cleaned, "Pandas")
    pandas_quality = cleaned_quality_pandas(pandas_cleaned)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = args.output.with_name(f"{args.output.name}.unverified")
    if temporary_output.exists():
        raise FileExistsError(f"기존 임시 파일이 있어 덮어쓰지 않습니다: {temporary_output}")
    finalized = False
    try:
        # Pandas 결과를 임시 저장하고 메모리를 해제한 뒤 Polars 처리를 시작한다.
        pandas_cleaned.to_parquet(temporary_output, index=False)
        del pandas_raw
        del pandas_cleaned
        gc.collect()

        polars_raw, polars_load, polars_parse_failures = load_one(args.input, "Polars")
        validate_polars_signature(load_signature, polars_raw)
        started = perf_counter()
        polars_eda = make_polars_eda(polars_raw)
        polars_eda_seconds = perf_counter() - started
        started = perf_counter()
        polars_cleaned, polars_metrics = clean_polars_data(polars_raw, args.input)
        polars_clean_seconds = perf_counter() - started
        validate_analysis_groups(polars_cleaned, "Polars")
        polars_quality = cleaned_quality_polars(polars_cleaned)
        del polars_raw
        gc.collect()
        load_comparison = pd.DataFrame({"Pandas": pandas_load, "Polars": polars_load})
        timings = pd.DataFrame(
            {
                "Pandas": [pandas_eda_seconds, pandas_clean_seconds],
                "Polars": [polars_eda_seconds, polars_clean_seconds],
            },
            index=["eda_seconds", "clean_seconds"],
        )
        result = compare_results(
            pandas_eda, polars_eda, pandas_metrics, polars_metrics,
            pandas_quality, polars_quality,
        )
        parse_failures = pd.DataFrame({
            "Pandas": pandas_parse_failures,
            "Polars": polars_parse_failures,
        }).fillna(0).astype(int)
        summary_metrics = [
            "raw_rows",
            "duplicate_rows_removed",
            "core_missing_rows_removed",
            "invalid_datetime_rows_removed",
            "nonpositive_duration_distance_or_fare_removed",
            "cleaned_rows",
        ]
        print("\n[Pandas/Polars 핵심 비교]")
        metric_comparison = pd.DataFrame({
            "Pandas": pandas_metrics,
            "Polars": polars_metrics,
        })
        print(metric_comparison.loc[summary_metrics].to_string())
        print("\n[정제·EDA 실행 시간(초), 단일 실행 참고값]")
        print(timings.to_string(float_format=lambda value: f"{value:,.4f}"))
        conclusion = (
            "일치"
            if result["matched"]
            else "불일치: " + ", ".join(result["differences"])
        )
        print(f"\n[검증 항목·정제 표본 비교 결론] {conclusion}")
        if not result["matched"]:
            write_report(
                args.report,
                args.input,
                load_comparison,
                pandas_eda,
                polars_eda,
                pandas_quality,
                pandas_metrics,
                polars_metrics,
                timings,
                result,
                date_quality,
                parse_failures,
            )
            print("Pandas·Polars 비교가 실패하여 최종 정제 파일을 확정하지 않았습니다.", file=sys.stderr)
            return 1
        # 두 구현의 검증 결과가 모두 일치할 때만 최종 파일로 확정한다.
        previous_output = args.output.with_name(f"{args.output.name}.previous")
        if previous_output.exists():
            raise FileExistsError(f"기존 백업 파일이 있어 덮어쓰지 않습니다: {previous_output}")
        previous_output_moved = False
        try:
            if args.output.exists():
                args.output.replace(previous_output)
                previous_output_moved = True
            temporary_output.replace(args.output)
            finalized = True
            write_report(
                args.report,
                args.input,
                load_comparison,
                pandas_eda,
                polars_eda,
                pandas_quality,
                pandas_metrics,
                polars_metrics,
                timings,
                result,
                date_quality,
                parse_failures,
            )
        except Exception:
            if previous_output_moved:
                try:
                    previous_output.replace(args.output)
                except OSError:
                    pass
            elif finalized:
                cleanup_temporary_output(args.output)
            finalized = False
            raise
        cleanup_temporary_output(previous_output)
        print(f"정제 데이터: {args.output} ({args.output.stat().st_size / 1024**2:,.1f} MB)")
        print(f"품질 보고서: {args.report}")
        return 0
    finally:
        if not finalized:
            cleanup_temporary_output(temporary_output)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, FileNotFoundError, AssertionError) as error:
        print(f"오류: {error}", file=sys.stderr)
        sys.exit(1)
