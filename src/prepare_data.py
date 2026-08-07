# 작성자: 최지윤
# 작성 목적: [종합실습 2] NYC Yellow Taxi 데이터를 Pandas·Polars로 로딩·비교하고 기본 EDA 및 분석용 정제 데이터를 생성
# 작성일: 2026-08-07
#
# 변경사항 내역 (날짜, 변경목적, 변경내용 순)
# 2026-08-07 : [데이터 준비 품질 강화] CSV 날짜 정규화, 표본 값 일관성 비교, 날짜·범주형 품질 진단을 보완
# 2026-08-07 : [실행 편의 개선] 입력 인수가 없으면 기본 Yellow Taxi 원본 경로를 사용하도록 CLI를 보완

from __future__ import annotations

import argparse
import random
import re
import sys
from pathlib import Path
from time import perf_counter

import pandas as pd
import polars as pl


REQUIRED_COLUMNS = {
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "trip_distance",
    "fare_amount",
}
PRESERVE_COLUMNS = REQUIRED_COLUMNS | {
    "total_amount",
    "extra",
    "RatecodeID",
    "PULocationID",
    "DOLocationID",
    "VendorID",
    "passenger_count",
}
CODE_COLUMNS = ["VendorID", "RatecodeID", "PULocationID", "DOLocationID"]
NUMERIC_COLUMNS = [
    "trip_distance",
    "fare_amount",
    "total_amount",
    "extra",
    "passenger_count",
]
# 이 경계는 자동 삭제 기준이 아니라, 후속 분석 단계에서 검토할 오류 후보 표시 기준이다.
LONG_TRIP_MINUTES = 24 * 60
LARGE_DISTANCE_MILES = 200
LARGE_FARE_DOLLARS = 1_000
MAX_PASSENGERS = 8
DATETIME_COLUMNS = ["tpep_pickup_datetime", "tpep_dropoff_datetime"]
SAMPLE_SIZE = 5
SAMPLE_SEED = 42
TOP_CATEGORY_VALUES = 20
DEFAULT_INPUT = Path("data/raw/yellow_tripdata_2025-01.parquet")


def load_frames(path: Path) -> tuple[pd.DataFrame, pl.DataFrame, pd.DataFrame]:
    """동일 파일을 각 라이브러리로 한 번씩 읽고 비교표를 반환한다."""
    readers = {
        ".parquet": (pd.read_parquet, pl.read_parquet),
        ".csv": (pd.read_csv, pl.read_csv),
        ".gz": (pd.read_csv, pl.read_csv),
    }
    try:
        pandas_reader, polars_reader = readers[path.suffix.lower()]
    except KeyError as exc:
        raise ValueError("지원 형식은 .parquet, .csv, .csv.gz입니다.") from exc

    started = perf_counter()
    pandas_df = pandas_reader(path)
    pandas_seconds = perf_counter() - started
    started = perf_counter()
    polars_df = polars_reader(path)
    polars_seconds = perf_counter() - started

    for column in DATETIME_COLUMNS:
        if column in pandas_df:
            pandas_df[column] = pd.to_datetime(pandas_df[column], errors="coerce")
        if column in polars_df and polars_df.schema[column] == pl.String:
            polars_df = polars_df.with_columns(
                pl.col(column).str.to_datetime(strict=False).alias(column)
            )

    comparison = pd.DataFrame(
        {
            "Pandas": [
                pandas_seconds,
                len(pandas_df),
                len(pandas_df.columns),
                pandas_df.memory_usage(index=True, deep=True).sum() / 1024**2,
            ],
            "Polars": [
                polars_seconds,
                polars_df.height,
                polars_df.width,
                polars_df.estimated_size("mb"),
            ],
        },
        index=["load_seconds", "rows", "columns", "memory_mb"],
    )
    return pandas_df, polars_df, comparison


def sample_indices(row_count: int) -> list[int]:
    """앞·뒤·고정 난수 표본의 재현 가능한 행 번호를 만든다."""
    if row_count == 0:
        return []
    edge_count = min(SAMPLE_SIZE, row_count)
    indices = set(range(edge_count)) | set(range(max(0, row_count - edge_count), row_count))
    random_count = min(SAMPLE_SIZE, row_count)
    indices.update(random.Random(SAMPLE_SEED).sample(range(row_count), random_count))
    return sorted(indices)


def normalize_sample(frame: pd.DataFrame) -> pd.DataFrame:
    """라이브러리별 nullable dtype 차이를 제외하고 실제 값을 비교 가능하게 만든다."""
    normalized = frame.reset_index(drop=True).copy()
    for column in normalized:
        if column in DATETIME_COLUMNS:
            normalized[column] = pd.to_datetime(normalized[column], errors="coerce")
        elif pd.api.types.is_numeric_dtype(normalized[column]):
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
        else:
            normalized[column] = normalized[column].astype("string")
    return normalized


def validate_loads(pandas_df: pd.DataFrame, polars_df: pl.DataFrame) -> dict[str, object]:
    if pandas_df.shape != polars_df.shape:
        raise AssertionError(f"행·열 수 불일치: {pandas_df.shape} != {polars_df.shape}")
    if list(pandas_df.columns) != polars_df.columns:
        raise AssertionError("Pandas와 Polars의 컬럼 순서가 다릅니다.")

    pandas_nulls = pandas_df.isna().sum().to_dict()
    polars_nulls = dict(zip(polars_df.columns, polars_df.null_count().row(0)))
    if pandas_nulls != polars_nulls:
        raise AssertionError("Pandas와 Polars의 컬럼별 결측치 수가 다릅니다.")

    indices = sample_indices(len(pandas_df))
    columns = [column for column in pandas_df.columns if column in PRESERVE_COLUMNS]
    pandas_sample = normalize_sample(pandas_df.iloc[indices][columns])
    polars_sample = normalize_sample(polars_df[indices].select(columns).to_pandas())
    try:
        pd.testing.assert_frame_equal(
            pandas_sample,
            polars_sample,
            check_dtype=False,
            check_exact=False,
            rtol=1e-12,
            atol=1e-12,
        )
    except AssertionError as exc:
        raise AssertionError("Pandas와 Polars의 주요 컬럼 표본 값이 다릅니다.") from exc
    return {"indices": indices, "columns": columns, "matched": True}


def expected_month(path: Path) -> pd.Period | None:
    match = re.search(r"(20\d{2})[-_](0[1-9]|1[0-2])", path.name)
    return pd.Period(f"{match.group(1)}-{match.group(2)}", freq="M") if match else None


def inspect_date_range(pickup: pd.Series, source_path: Path) -> dict[str, object]:
    valid_pickup = pd.to_datetime(pickup, errors="coerce").dropna()
    month_counts = valid_pickup.dt.to_period("M").value_counts().sort_index()
    source_month = expected_month(source_path)
    outside_count = None
    if source_month is not None:
        outside_count = int(valid_pickup.dt.to_period("M").ne(source_month).sum())
    return {
        "source_month": str(source_month) if source_month is not None else None,
        "actual_month_count": len(month_counts),
        "has_multiple_months": len(month_counts) > 1,
        "actual_month_distribution": month_counts,
        "outside_source_month_rows": outside_count,
    }


def summarize_categories(raw_df: pd.DataFrame) -> pd.DataFrame:
    categorical = list(raw_df.select_dtypes(include=["object", "string", "category"]).columns)
    summaries = []
    for column in categorical:
        counts = raw_df[column].value_counts(dropna=False).head(TOP_CATEGORY_VALUES)
        summary = counts.rename("count").to_frame()
        summary["ratio_pct"] = summary["count"].div(len(raw_df)).mul(100)
        summary["unique_count"] = raw_df[column].nunique(dropna=False)
        summary["missing_count"] = raw_df[column].isna().sum()
        summary.index = summary.index.astype(str)
        summaries.append(pd.concat({column: summary}, names=["column", "value"]))
    return pd.concat(summaries) if summaries else pd.DataFrame(
        columns=["count", "ratio_pct", "unique_count", "missing_count"]
    )


def make_eda(raw_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    row_count = len(raw_df)
    missing = raw_df.isna().sum().rename("missing_count").to_frame()
    missing["missing_ratio_pct"] = missing["missing_count"].div(row_count).mul(100)
    numeric = [column for column in NUMERIC_COLUMNS if column in raw_df]
    codes = [column for column in CODE_COLUMNS if column in raw_df]
    datetime_columns = list(raw_df.select_dtypes(include=["datetime", "datetimetz"]).columns)

    return {
        "schema": pd.DataFrame({"dtype": raw_df.dtypes.astype(str)}),
        "missing": missing,
        "numeric_summary": raw_df[numeric].describe(percentiles=[0.25, 0.5, 0.75]).T,
        "datetime_range": pd.DataFrame(
            {"min": raw_df[datetime_columns].min(), "max": raw_df[datetime_columns].max()}
        ),
        "category_distribution": summarize_categories(raw_df),
        "code_distribution": pd.concat(
            {
                column: raw_df[column].value_counts(dropna=False).head(20)
                for column in codes
            },
            names=["column", "value"],
        ).rename("count").to_frame(),
    }


def clean_data(raw_df: pd.DataFrame, source_path: Path) -> tuple[pd.DataFrame, dict[str, int]]:
    missing_columns = sorted(REQUIRED_COLUMNS - set(raw_df.columns))
    if missing_columns:
        raise ValueError(f"필수 컬럼이 없습니다: {', '.join(missing_columns)}")

    cleaned_df = raw_df.drop_duplicates().copy()
    core_missing = cleaned_df[list(REQUIRED_COLUMNS)].isna().any(axis=1)
    cleaned_df = cleaned_df.loc[~core_missing].copy()

    cleaned_df["tpep_pickup_datetime"] = pd.to_datetime(
        cleaned_df["tpep_pickup_datetime"], errors="coerce"
    )
    cleaned_df["tpep_dropoff_datetime"] = pd.to_datetime(
        cleaned_df["tpep_dropoff_datetime"], errors="coerce"
    )
    pickup = cleaned_df["tpep_pickup_datetime"]
    dropoff = cleaned_df["tpep_dropoff_datetime"]
    invalid_datetime = pickup.isna() | dropoff.isna()
    cleaned_df = cleaned_df.loc[~invalid_datetime].copy()
    pickup = pickup.loc[~invalid_datetime]
    dropoff = dropoff.loc[~invalid_datetime]

    duration = (dropoff - pickup).dt.total_seconds().div(60)
    invalid_duration = duration.le(0)
    invalid_distance = cleaned_df["trip_distance"].le(0)
    invalid_fare = cleaned_df["fare_amount"].le(0)
    objectively_invalid = invalid_duration | invalid_distance | invalid_fare
    cleaned_df = cleaned_df.loc[~objectively_invalid].copy()
    duration = duration.loc[~objectively_invalid]
    pickup = pickup.loc[~objectively_invalid]

    cleaned_df["trip_duration_min"] = duration
    cleaned_df["pickup_hour"] = pickup.dt.hour.astype("int8")
    cleaned_df["day_of_week"] = pickup.dt.day_name()
    cleaned_df["is_weekday"] = pickup.dt.dayofweek.lt(5)
    cleaned_df["is_long_trip_candidate"] = duration.gt(LONG_TRIP_MINUTES)
    cleaned_df["is_large_distance_candidate"] = cleaned_df["trip_distance"].gt(
        LARGE_DISTANCE_MILES
    )
    cleaned_df["is_large_fare_candidate"] = cleaned_df["fare_amount"].gt(
        LARGE_FARE_DOLLARS
    )
    if "passenger_count" in cleaned_df:
        cleaned_df["is_invalid_passenger_candidate"] = (
            cleaned_df["passenger_count"].le(0)
            | cleaned_df["passenger_count"].gt(MAX_PASSENGERS)
        ).fillna(False)

    month = expected_month(source_path)
    if month:
        month_start = month.start_time
        month_end = (month + 1).start_time
        cleaned_df["is_outside_source_month"] = ~pickup.between(
            month_start, month_end, inclusive="left"
        )

    metrics = {
        "raw_rows": len(raw_df),
        "duplicate_rows_removed": int(raw_df.duplicated().sum()),
        "core_missing_rows_removed": int(core_missing.sum()),
        "invalid_datetime_rows_removed": int(invalid_datetime.sum()),
        "nonpositive_duration_rows": int(invalid_duration.sum()),
        "nonpositive_distance_rows": int(invalid_distance.sum()),
        "nonpositive_fare_rows": int(invalid_fare.sum()),
        "nonpositive_duration_distance_or_fare_removed": int(objectively_invalid.sum()),
        "cleaned_rows": len(cleaned_df),
    }
    return cleaned_df, metrics


def write_report(
    path: Path,
    source: Path,
    raw_df: pd.DataFrame,
    polars_df: pl.DataFrame,
    comparison: pd.DataFrame,
    eda: dict[str, pd.DataFrame],
    cleaned_df: pd.DataFrame,
    metrics: dict[str, int],
    load_validation: dict[str, object],
    date_quality: dict[str, object],
) -> None:
    duplicate_count = int(raw_df.duplicated().sum())
    candidate_columns = [
        column
        for column in cleaned_df
        if column.endswith("_candidate") or column == "is_outside_source_month"
    ]
    lines = [
        "# 데이터 품질 및 전처리 결과",
        "",
        f"- 원본: `{source}`",
        f"- 크기: {raw_df.shape[0]:,}행 × {raw_df.shape[1]:,}열",
        f"- 완전 중복: {duplicate_count:,}행 ({duplicate_count / len(raw_df):.4%})",
        f"- Pandas/Polars 로딩 일관성: 통과 (크기, 컬럼 순서, 결측치 수, 표본 실제 값)",
        f"- 값 비교 표본: 앞·뒤 각 최대 {SAMPLE_SIZE}행과 seed={SAMPLE_SEED} 고정 표본, "
        f"주요 {len(load_validation['columns'])}개 컬럼, 총 {len(load_validation['indices'])}행",
        "- 로딩 시간: 각 라이브러리 1회 측정 참고값 (OS 파일 캐시에 따라 변동)",
        "",
        "## Pandas와 Polars 비교",
        "",
        comparison.to_markdown(floatfmt=".3f"),
        "",
        "### Pandas dtype",
        "",
        eda["schema"].to_markdown(),
        "",
        "### Polars dtype",
        "",
        pd.DataFrame({"dtype": [str(dtype) for dtype in polars_df.dtypes]}, index=polars_df.columns).to_markdown(),
        "",
        "### Pandas 앞 5행",
        "",
        raw_df.head().to_markdown(index=False),
        "",
        "### Polars 앞 5행",
        "",
        polars_df.head().to_pandas().to_markdown(index=False),
        "",
        "## 결측치",
        "",
        eda["missing"].to_markdown(floatfmt=".4f"),
        "",
        "## 주요 수치형 기초 통계",
        "",
        eda["numeric_summary"].to_markdown(floatfmt=".3f"),
        "",
        "## 날짜 범위",
        "",
        eda["datetime_range"].to_markdown(),
        "",
        "## 범주형 주요 값 분포 (각 상위 20개)",
        "",
        eda["category_distribution"].to_markdown(floatfmt=".4f"),
        "",
        "## 주요 코드 분포 (각 상위 20개)",
        "",
        eda["code_distribution"].to_markdown(),
        "",
        "## 기준 연월 및 실제 날짜 분포",
        "",
        f"- 파일명 기준 연월: `{date_quality['source_month'] or '추출 불가'}`",
        f"- 실제 연월 수: {date_quality['actual_month_count']}",
        f"- 여러 연월 혼재: {date_quality['has_multiple_months']}",
        f"- 기준 연월 밖 행: {date_quality['outside_source_month_rows'] if date_quality['outside_source_month_rows'] is not None else '판정하지 않음'}",
        "",
        date_quality["actual_month_distribution"].rename("rows").to_frame().to_markdown(),
        "",
        "## 처리 전후",
        "",
        pd.Series(metrics, name="count").to_frame().to_markdown(),
        "",
        "## 보존된 오류 후보",
        "",
        pd.Series(
            {column: int(cleaned_df[column].sum()) for column in candidate_columns},
            name="rows",
        ).to_frame().to_markdown(),
        "",
        "후보 기준은 절대적인 오류 판정이 아닌 보수적인 임시 검토 기준이므로 삭제하지 않았습니다. `is_rush_hour`는 팀 기준 확정 후 생성합니다.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def verify(raw_df: pd.DataFrame, cleaned_df: pd.DataFrame) -> None:
    assert len(cleaned_df) <= len(raw_df), "정제 데이터가 원본보다 많습니다."
    assert not cleaned_df.duplicated().any(), "완전 중복 행이 남아 있습니다."
    assert not cleaned_df[list(REQUIRED_COLUMNS)].isna().any().any(), "핵심 컬럼 결측치가 남아 있습니다."
    assert PRESERVE_COLUMNS.intersection(raw_df.columns) <= set(cleaned_df.columns), "보존 대상 컬럼이 누락됐습니다."
    recalculated = (
        cleaned_df["tpep_dropoff_datetime"] - cleaned_df["tpep_pickup_datetime"]
    ).dt.total_seconds().div(60)
    assert cleaned_df["trip_duration_min"].equals(recalculated), "운행시간 계산이 일치하지 않습니다."


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


def main() -> int:
    args = parse_args()
    if not args.input.is_file():
        raise FileNotFoundError(
            f"입력 데이터 파일을 찾을 수 없습니다: {args.input}. "
            f"기본 실행에는 '{DEFAULT_INPUT}' 파일이 필요하며, 다른 파일은 첫 번째 인수로 지정하세요."
        )

    raw_df, polars_df, comparison = load_frames(args.input)
    load_validation = validate_loads(raw_df, polars_df)
    print("\n[Pandas/Polars 로딩 비교]")
    print(comparison.to_string(float_format=lambda value: f"{value:,.3f}"))
    print("\n[Pandas 앞 5행]")
    print(raw_df.head().to_string(index=False))
    print("\n[Polars 앞 5행]")
    print(polars_df.head())

    cleaned_df, metrics = clean_data(raw_df, args.input)
    eda = make_eda(raw_df)
    date_quality = inspect_date_range(raw_df["tpep_pickup_datetime"], args.input)
    verify(raw_df, cleaned_df)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    cleaned_df.to_parquet(args.output, index=False)
    write_report(
        args.report,
        args.input,
        raw_df,
        polars_df,
        comparison,
        eda,
        cleaned_df,
        metrics,
        load_validation,
        date_quality,
    )
    print("\n[처리 결과]")
    print(pd.Series(metrics).to_string())
    print(f"정제 데이터: {args.output} ({args.output.stat().st_size / 1024**2:,.1f} MB)")
    print(f"품질 보고서: {args.report}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, FileNotFoundError, AssertionError) as error:
        print(f"오류: {error}", file=sys.stderr)
        sys.exit(1)
