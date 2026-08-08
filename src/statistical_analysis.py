"""
작성자: 임동건
작성일: 2026.08.07
파일명: statistical_analysis.py

NYC Yellow Taxi 출퇴근 시간대 통계 분석

최초 작성

- Yellow Taxi 정제 데이터 로딩 및 2026년 5월 데이터 필터링
- 날짜 기준 Discovery / Validation 데이터 분리
- 평일·주말 시간대별 운행량 및 extra 분포 분석
- 출퇴근 / 비출퇴근 구간 파생변수 및 평균 이동속도 계산
- 기술통계, 상관분석, 웰치의 t-test 구현

분석 원칙

- 출퇴근 시간대 설정:
  외부 자료를 기준으로 오전·오후 출퇴근 시간대를 정의하고,
  Discovery 데이터의 평일/주말 운행량과 extra 분포를 통해
  실제 Yellow Taxi 데이터에서도 관련 패턴이 나타나는지 확인
- 결과 검정:
  trip_duration_min, fare_amount, total_amount 사용
- 검정 대상:
  공휴일을 제외한 평일 운행만 사용

변경 사항
- 2026년 5월 데이터만 사용
- 출근 시간 정의: 06:00 ~ 10:00
- 퇴근 시간 정의: 16:00 ~ 20:00
- 극단값 후보 [is_long_trip_candidate,
  is_large_distance_candidate, is_large_fare_candidate]
  제외하고 다시 분석
- 운행시간 이상치 때문에 속도 오염
  이상치 필터링 하는 것 보다
  상광분석, 기술통계 변수에서 속도 제외
- TTEST에 trip_distance 추가
- 거리 통제 다변량 회귀 및 Partial F-test 추가
- RatecodeID 추가 (일반운행만 필터링용)
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import pandas as pd
from scipy.stats import ttest_ind
import statsmodels.api as sm

# =========================================================
# 기본 설정
# =========================================================

DEFAULT_INPUT = Path("data/processed/yellow_taxi_cleaned.parquet")

DEFAULT_OUTPUT_DIR = Path("reports/generated/statistics")

RANDOM_SEED = 42
ALPHA = 0.05


# 통계 분석에 필요한 컬럼만 읽기
# ANALYSIS_COLUMNS = [
#     "tpep_pickup_datetime",
#     "trip_duration_min",
#     "trip_distance",
#     "fare_amount",
#     "total_amount",
#     "extra",
# ]

# 극단치 고려
ANALYSIS_COLUMNS = [
    "tpep_pickup_datetime",
    "trip_duration_min",
    "trip_distance",
    "fare_amount",
    "total_amount",
    "extra",
    "RatecodeID",
    "is_long_trip_candidate",
    "is_large_distance_candidate",
    "is_large_fare_candidate",
]


# 2026년 5월의 출퇴근 패턴 분석에서 제외할 공휴일
#
# 주말 취급?
HOLIDAYS = {
    pd.Timestamp("2026-05-25"),
}


# =========================================================
# 출퇴근 시간대 설정
# =========================================================
#
# 출근 시간: 06:00 ~ 10:00
# - 외부 자료의 주요 출근 시간 06:30 ~ 09:30 참고
# - 시간 단위 분석을 위해 06:00 ~ 10:00으로 확장
# - Discovery 데이터에서도 평일 운행량 증가 확인
#
# 퇴근 시간: 16:00 ~ 20:00
# - TLC 공식 평일 러시아워 기준
# - Discovery extra 분포에서도 정책 패턴 확인


COMMUTE_WINDOWS = {
    "morning": (6, 10),
    "evening": (16, 20),
}


# =========================================================
# 분석 변수
# =========================================================

DESCRIPTIVE_COLUMNS = [
    "trip_distance",
    "trip_duration_min",
    "fare_amount",
    "total_amount",
]

CORRELATION_COLUMNS = [
    "trip_distance",
    "trip_duration_min",
    "fare_amount",
    "total_amount",
    "extra",
]

TTEST_COLUMNS = [
    "trip_distance",
    "trip_duration_min",
    "fare_amount",
    "total_amount",
]


# =========================================================
# 데이터 로딩
# =========================================================


def load_data(path: Path) -> pd.DataFrame:
    """
    정제된 Yellow Taxi Parquet에서
    통계 분석에 필요한 컬럼만 읽는다.
    """

    if not path.exists():
        raise FileNotFoundError(f"분석 데이터 파일을 찾을 수 없습니다: {path}")

    df = pd.read_parquet(
        path,
        columns=ANALYSIS_COLUMNS,
    )

    df["tpep_pickup_datetime"] = pd.to_datetime(
        df["tpep_pickup_datetime"],
        errors="coerce",
    )

    # datetime 변환에 실패한 행 제거
    df = df.dropna(subset=["tpep_pickup_datetime"]).copy()

    # -----------------------------------------------------
    # 분석 대상 기간 제한
    # -----------------------------------------------------
    # 본 프로젝트는 2026년 5월 Yellow Taxi 데이터를
    # 분석하므로 pickup 시각을 기준으로 해당 월만 사용한다.
    #
    # 5월 31일에 승차하여 6월 1일에 하차한 정상 운행은 포함
    # -----------------------------------------------------

    analysis_start = pd.Timestamp("2026-05-01")
    analysis_end = pd.Timestamp("2026-06-01")

    df = df.loc[
        (df["tpep_pickup_datetime"] >= analysis_start)
        & (df["tpep_pickup_datetime"] < analysis_end)
    ].copy()

    if df.empty:
        raise ValueError("2026년 5월 분석 대상 데이터가 없습니다.")

    return df


# =========================================================
# 날짜·시간 파생변수 생성
# =========================================================


def add_calendar_features(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    날짜 단위 분할과 평일/주말 비교를 위한
    시간 관련 파생변수를 생성한다.
    """

    result = df.copy()

    result["pickup_date"] = result["tpep_pickup_datetime"].dt.normalize()

    result["pickup_hour"] = result["tpep_pickup_datetime"].dt.hour

    result["is_weekday"] = result["tpep_pickup_datetime"].dt.dayofweek < 5

    result["is_holiday"] = result["pickup_date"].isin(HOLIDAYS)

    # 일반적인 통근 분석 대상으로 사용할 영업일
    result["is_business_day"] = result["is_weekday"] & ~result["is_holiday"]

    # # 공휴일 주말 취급할지말지
    # result["day_type"] = "business_day"

    # result.loc[
    #     ~result["is_weekday"],
    #     "day_type",
    # ] = "weekend"

    # result.loc[
    #     result["is_holiday"],
    #     "day_type",
    # ] = "holiday"

    # result["is_non_business_day"] = ~result["is_business_day"]

    return result


# =========================================================
# Discovery / Validation 분할
# =========================================================


def split_by_date(
    df: pd.DataFrame,
    random_seed: int = RANDOM_SEED,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    """
    데이터를 행 단위가 아닌 날짜 단위로 분리한다.

    평일과 주말 날짜를 각각 섞은 후 약 절반씩
    Discovery와 Validation에 배정한다.

    공휴일은 출퇴근 패턴 분석 대상에서 제외한다.
    """

    usable_df = df.loc[~df["is_holiday"]].copy()

    date_table = (
        usable_df[
            [
                "pickup_date",
                "is_weekday",
            ]
        ]
        .drop_duplicates()
        .sort_values("pickup_date")
        .reset_index(drop=True)
    )

    rng = random.Random(random_seed)

    discovery_dates: list[pd.Timestamp] = []
    validation_dates: list[pd.Timestamp] = []

    # 평일과 주말을 각각 나누어
    # 두 데이터셋의 구성 차이를 줄인다.
    for is_weekday in (True, False):
        dates = date_table.loc[
            date_table["is_weekday"] == is_weekday,
            "pickup_date",
        ].tolist()

        rng.shuffle(dates)

        # 홀수 개 날짜인 경우 Discovery가 1일 더 갖는다.
        split_index = (len(dates) + 1) // 2

        discovery_dates.extend(dates[:split_index])

        validation_dates.extend(dates[split_index:])

    discovery_df = usable_df.loc[usable_df["pickup_date"].isin(discovery_dates)].copy()

    validation_df = usable_df.loc[
        usable_df["pickup_date"].isin(validation_dates)
    ].copy()

    split_table = date_table.copy()

    split_table["split"] = split_table["pickup_date"].apply(
        lambda date: ("discovery" if date in discovery_dates else "validation")
    )

    split_table["day_type"] = split_table["is_weekday"].map(
        {
            True: "weekday",
            False: "weekend",
        }
    )

    return (
        discovery_df,
        validation_df,
        split_table,
    )


# =========================================================
# Discovery 1
# 시간별 운행량 분석
# =========================================================


def make_hourly_demand_profile(
    discovery_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    평일과 주말의 시간별 평균 일일 운행량을 계산한다.

    단순 총 운행량은 평일/주말 날짜 수 차이에 영향을 받으므로,
    먼저 날짜별 시간대 운행량을 계산한 뒤 일평균을 구한다.
    """

    # 날짜 × 시간별 실제 운행 횟수
    daily_counts = (
        discovery_df.groupby(
            [
                "pickup_date",
                "is_weekday",
                "pickup_hour",
            ],
            as_index=False,
        )
        .size()
        .rename(
            columns={
                "size": "trip_count",
            }
        )
    )

    # 평일 / 주말의 시간별 일평균 운행량
    hourly_summary = daily_counts.groupby(
        [
            "is_weekday",
            "pickup_hour",
        ],
        as_index=False,
    ).agg(
        avg_daily_trip_count=(
            "trip_count",
            "mean",
        ),
        median_daily_trip_count=(
            "trip_count",
            "median",
        ),
        days_observed=(
            "pickup_date",
            "nunique",
        ),
    )

    # 평일·주말 비교가 쉽도록 wide format으로 변환
    avg_pivot = (
        hourly_summary.pivot(
            index="pickup_hour",
            columns="is_weekday",
            values="avg_daily_trip_count",
        )
        .rename(
            columns={
                False: "weekend_avg_trips",
                True: "weekday_avg_trips",
            }
        )
        .reset_index()
    )

    # 혹시 특정 그룹이 존재하지 않는 경우를 대비
    for column in [
        "weekday_avg_trips",
        "weekend_avg_trips",
    ]:
        if column not in avg_pivot:
            avg_pivot[column] = pd.NA

    # 평일과 주말의 절대적인 운행량 차이
    avg_pivot["weekday_lift"] = (
        avg_pivot["weekday_avg_trips"] - avg_pivot["weekend_avg_trips"]
    )

    # 평일 운행량이 주말의 몇 배인지 확인
    denominator = avg_pivot["weekend_avg_trips"].where(
        avg_pivot["weekend_avg_trips"] != 0
    )

    avg_pivot["weekday_to_weekend_ratio"] = avg_pivot["weekday_avg_trips"] / denominator

    return avg_pivot.sort_values("pickup_hour").reset_index(drop=True)


# =========================================================
# Discovery 2
# extra 분포 확인
# =========================================================


def make_extra_distribution(
    discovery_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    시간대별 extra 값 분포를 계산한다.

    extra로 출퇴근 시간을 직접 결정하지 않고,
    TLC 공식 러시아워 및 데이터 기반 후보 시간대와
    비교하기 위한 보조 자료로만 사용한다.
    """

    extra_df = (
        discovery_df[
            [
                "is_weekday",
                "pickup_hour",
                "extra",
            ]
        ]
        .dropna()
        .copy()
    )

    # 실수 표현 오차를 줄이기 위해 소수 둘째 자리까지 반올림
    extra_df["extra_value"] = extra_df["extra"].round(2)

    extra_df["day_type"] = extra_df["is_weekday"].map(
        {
            True: "weekday",
            False: "weekend",
        }
    )

    distribution = (
        extra_df.groupby(
            [
                "day_type",
                "pickup_hour",
                "extra_value",
            ],
            as_index=False,
        )
        .size()
        .rename(
            columns={
                "size": "count",
            }
        )
    )

    # 같은 시간대 내에서 해당 extra 값이 차지하는 비율
    distribution["share"] = distribution["count"] / distribution.groupby(
        [
            "day_type",
            "pickup_hour",
        ]
    )["count"].transform("sum")

    return distribution.sort_values(
        [
            "day_type",
            "pickup_hour",
            "count",
        ],
        ascending=[
            True,
            True,
            False,
        ],
    ).reset_index(drop=True)


# =========================================================
# Validation 분석 준비
# =========================================================


def validate_commute_windows() -> None:
    """
    출퇴근 시간 설정값이 정상적인지 확인한다.
    """

    for name, (start, end) in COMMUTE_WINDOWS.items():
        if not (0 <= start < end <= 24):
            raise ValueError(f"{name} 시간 범위가 잘못되었습니다: " f"({start}, {end})")


def add_commute_features(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    확정된 출퇴근 시간대를 Validation 데이터에 적용한다.
    """

    validate_commute_windows()

    result = df.copy()

    result["is_commute_hour"] = False
    result["commute_period"] = "non_commute"

    for name, (start, end) in COMMUTE_WINDOWS.items():
        mask = result["pickup_hour"].ge(start) & result["pickup_hour"].lt(end)

        result.loc[
            mask,
            "is_commute_hour",
        ] = True

        result.loc[
            mask,
            "commute_period",
        ] = name

    result["commute_group"] = result["is_commute_hour"].map(
        {
            True: "commute",
            False: "non_commute",
        }
    )

    return result


# def add_speed(
#     df: pd.DataFrame,
# ) -> pd.DataFrame:
#     """
#     이동거리와 이동시간을 이용해 평균 이동속도(mph)를 계산한다.

#     speed_mph는 출퇴근 시간대 선정에는 사용하지 않고
#     Validation 결과 해석에만 사용한다.
#     """

#     result = df.copy()

#     result["speed_mph"] = result["trip_distance"] / (result["trip_duration_min"] / 60)

#     return result


# =========================================================
# 기술통계
# =========================================================


def make_descriptive_statistics(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    출퇴근 / 비출퇴근 그룹별 기술통계를 산출한다.
    """

    return (
        df.groupby("commute_group")[DESCRIPTIVE_COLUMNS]
        .describe(
            percentiles=[
                0.25,
                0.50,
                0.75,
            ]
        )
        .round(4)
    )


# =========================================================
# 상관분석
# =========================================================


def make_correlation_matrix(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    주요 숫자형 변수 간 Pearson 상관계수를 계산한다.
    """

    return df[CORRELATION_COLUMNS].corr(method="pearson").round(4)


# =========================================================
# Welch's t-test
# =========================================================


def run_welch_ttests(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    출퇴근 시간대와 비출퇴근 시간대의 평균 차이를
    Welch's independent t-test로 검정한다.
    """

    results: list[dict[str, object]] = []

    for column in TTEST_COLUMNS:
        commute = df.loc[
            df["is_commute_hour"],
            column,
        ].dropna()

        non_commute = df.loc[
            ~df["is_commute_hour"],
            column,
        ].dropna()

        if len(commute) < 2 or len(non_commute) < 2:
            raise ValueError(f"{column}: t-test에 필요한 " "표본 수가 부족합니다.")

        test_result = ttest_ind(
            commute,
            non_commute,
            equal_var=False,
            nan_policy="omit",
        )

        t_statistic = float(test_result.statistic)

        p_value = float(test_result.pvalue)

        commute_mean = float(commute.mean())

        non_commute_mean = float(non_commute.mean())

        mean_difference = commute_mean - non_commute_mean

        reject_h0 = p_value < ALPHA

        results.append(
            {
                "variable": column,
                "commute_n": len(commute),
                "non_commute_n": len(non_commute),
                "commute_mean": commute_mean,
                "non_commute_mean": (non_commute_mean),
                "mean_difference": (mean_difference),
                "t_statistic": t_statistic,
                "p_value": p_value,
                "alpha": ALPHA,
                "reject_h0": reject_h0,
                "interpretation": (
                    "통계적으로 유의한 평균 차이"
                    if reject_h0
                    else "통계적으로 유의한 " "평균 차이를 확인하지 못함"
                ),
            }
        )

    return pd.DataFrame(results)


# =========================================================
# 거리 통제 다변량 회귀 및 Partial F-test
# =========================================================


def run_distance_adjusted_regression(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    이동거리를 통제한 상태에서 출퇴근 시간대 여부가
    이동시간 설명에 추가적인 정보를 제공하는지 검정한다.

    Reduced model:
        trip_duration_min ~ trip_distance

    Full model:
        trip_duration_min ~ trip_distance + is_commute_hour

    두 nested model을 Partial F-test로 비교한다.
    """

    analysis_df = (
        df[
            [
                "trip_duration_min",
                "trip_distance",
                "is_commute_hour",
            ]
        ]
        .dropna()
        .copy()
    )

    if len(analysis_df) < 3:
        raise ValueError("거리 통제 회귀분석에 필요한 표본 수가 부족합니다.")

    # bool 값을 회귀분석용 0/1 변수로 변환
    analysis_df["is_commute_hour"] = analysis_df["is_commute_hour"].astype(int)

    y = analysis_df["trip_duration_min"]

    # -----------------------------------------------------
    # Reduced model
    # 이동거리만으로 이동시간 설명
    # -----------------------------------------------------

    reduced_x = sm.add_constant(
        analysis_df[
            [
                "trip_distance",
            ]
        ]
    )

    reduced_model = sm.OLS(
        y,
        reduced_x,
    ).fit()

    # -----------------------------------------------------
    # Full model
    # 이동거리 + 출퇴근 여부로 이동시간 설명
    # -----------------------------------------------------

    full_x = sm.add_constant(
        analysis_df[
            [
                "trip_distance",
                "is_commute_hour",
            ]
        ]
    )

    full_model = sm.OLS(
        y,
        full_x,
    ).fit()

    # -----------------------------------------------------
    # Partial F-test
    # Full model이 Reduced model보다
    # 유의하게 설명력을 개선하는지 검정
    # -----------------------------------------------------

    f_statistic, p_value, df_difference = full_model.compare_f_test(reduced_model)

    # 출퇴근 여부 회귀계수와 95% 신뢰구간
    rush_coefficient = float(full_model.params["is_commute_hour"])

    confidence_interval = full_model.conf_int(alpha=ALPHA).loc["is_commute_hour"]

    ci_low = float(confidence_interval.iloc[0])
    ci_high = float(confidence_interval.iloc[1])

    reduced_r2 = float(reduced_model.rsquared)
    full_r2 = float(full_model.rsquared)
    delta_r2 = full_r2 - reduced_r2

    reject_h0 = float(p_value) < ALPHA

    result = pd.DataFrame(
        [
            {
                "target": "trip_duration_min",
                "n": len(analysis_df),
                "reduced_r2": reduced_r2,
                "full_r2": full_r2,
                "delta_r2": delta_r2,
                "distance_coefficient": float(full_model.params["trip_distance"]),
                "rush_coefficient": rush_coefficient,
                "rush_ci_low": ci_low,
                "rush_ci_high": ci_high,
                "partial_f_statistic": float(f_statistic),
                "df_difference": float(df_difference),
                "p_value": float(p_value),
                "alpha": ALPHA,
                "reject_h0": reject_h0,
                "interpretation": (
                    "출퇴근 여부 추가 효과는 통계적으로 유의함"
                    if reject_h0
                    else "출퇴근 여부의 통계적으로 유의한 추가 효과를 확인하지 못함"
                ),
            }
        ]
    )

    return result


# =========================================================
# Standard rate 민감도 분석 준비
# =========================================================


def filter_standard_rate(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    RatecodeID == 1인 Standard rate 운행만 선택한다.

    특수 요금 체계가 기존 출퇴근 / 비출퇴근 비교 결과에
    영향을 주었는지 확인하기 위한 민감도 분석에 사용한다.
    """

    result = df.loc[df["RatecodeID"] == 1].copy()

    if result.empty:
        raise ValueError("RatecodeID == 1인 Standard rate 데이터가 없습니다.")

    return result


# =========================================================
# 결과 저장
# =========================================================


def save_result(
    df: pd.DataFrame,
    path: Path,
    index: bool = False,
) -> None:
    """
    결과 DataFrame을 CSV 파일로 저장한다.
    """

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_csv(
        path,
        index=index,
        encoding="utf-8",
    )


# =========================================================
# Main
# =========================================================


def main() -> int:
    parser = argparse.ArgumentParser(
        description=("NYC Yellow Taxi " "출퇴근 시간대 통계 분석")
    )

    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="EDA 단계에서 생성한 cleaned parquet 경로",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="통계 분석 결과 저장 디렉토리",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=RANDOM_SEED,
        help="날짜 분할 재현성을 위한 random seed",
    )

    args = parser.parse_args()

    try:
        # -------------------------------------------------
        # 1. 정제 데이터 로딩
        # -------------------------------------------------

        df = load_data(args.input)
        df = add_calendar_features(df)

        print("=" * 60)
        print("NYC Yellow Taxi 통계 분석")
        print("=" * 60)

        print(f"\n전체 데이터 행 수: " f"{len(df):,}")

        print(
            f"분석 기간: "
            f"{df['pickup_date'].min().date()} "
            f"~ "
            f"{df['pickup_date'].max().date()}"
        )

        # -------------------------------------------------
        # 2. Discovery / Validation 분리
        # -------------------------------------------------

        (
            discovery_df,
            validation_df,
            split_table,
        ) = split_by_date(
            df,
            random_seed=args.seed,
        )

        print(f"\nDiscovery 행 수 : " f"{len(discovery_df):,}")

        print(f"Validation 행 수: " f"{len(validation_df):,}")

        save_result(
            split_table,
            args.output_dir / "split_dates.csv",
        )

        # -------------------------------------------------
        # 3. Discovery - 시간별 운행량
        # -------------------------------------------------

        hourly_profile = make_hourly_demand_profile(discovery_df)

        save_result(
            hourly_profile,
            args.output_dir / "hourly_demand_profile.csv",
        )

        print("\n[Discovery - " "평일/주말 시간별 평균 운행량]")

        print(hourly_profile.to_string(index=False))

        # -------------------------------------------------
        # 4. Discovery - extra 분포
        # -------------------------------------------------

        extra_distribution = make_extra_distribution(discovery_df)

        save_result(
            extra_distribution,
            args.output_dir / "extra_distribution_by_hour.csv",
        )

        print("\nDiscovery 결과가 생성되었습니다.")

        print(
            "외부 자료로 설정한 출퇴근 시간대와 "
            "Discovery 데이터의 패턴을 확인했습니다."
        )

        # -------------------------------------------------
        # 출퇴근 시간대가 아직 확정되지 않았다면
        # Validation 데이터는 분석하지 않는다.
        # -------------------------------------------------

        if not COMMUTE_WINDOWS:
            print(
                "\nCOMMUTE_WINDOWS가 비어 있으므로 "
                "Validation 분석은 실행하지 않습니다."
            )

            print(
                "이는 Validation 데이터를 먼저 보고 "
                "출퇴근 시간대를 수정하는 "
                "데이터 스누핑을 방지하기 위한 것입니다."
            )

            return 0

        # -------------------------------------------------
        # 5. Validation 분석
        # -------------------------------------------------
        #
        # 주말과 평일을 섞어 비교하면
        # 출퇴근 시간 효과와 요일 효과가 섞일 수 있으므로
        # 공휴일을 제외한 평일만 검정에 사용한다.
        # -------------------------------------------------

        validation_business = validation_df.loc[validation_df["is_business_day"]].copy()

        # -------------------------------------------------
        # 기존 EDA 단계에서 정의된 극단값 후보 제외
        # -------------------------------------------------

        candidate_columns = [
            "is_long_trip_candidate",
            "is_large_distance_candidate",
            "is_large_fare_candidate",
        ]

        candidate_mask = (
            validation_business[candidate_columns]
            .fillna(False)
            .astype(bool)
            .any(axis=1)
        )

        print("\n[Validation 극단값 후보 제외]")
        print(f"제외 전: {len(validation_business):,}행")

        for column in candidate_columns:
            count = validation_business[column].fillna(False).astype(bool).sum()

            print(f"- {column}: {count:,}행")

        print(f"- 중복을 제거한 실제 제외 대상: " f"{candidate_mask.sum():,}행")

        validation_analysis = validation_business.loc[~candidate_mask].copy()

        print(f"제외 후: {len(validation_analysis):,}행")

        # -------------------------------------------------
        # 출퇴근 구분
        # -------------------------------------------------

        validation_analysis = add_commute_features(validation_analysis)

        # validation_analysis = add_speed(validation_analysis)

        # -------------------------------------------------
        # 6. 기술통계
        # -------------------------------------------------

        descriptive = make_descriptive_statistics(validation_analysis)

        save_result(
            descriptive,
            args.output_dir / "descriptive_statistics.csv",
            index=True,
        )

        print("\n[출퇴근 / 비출퇴근 기술통계]")

        print(descriptive)

        # -------------------------------------------------
        # 7. 상관계수
        # -------------------------------------------------

        correlation = make_correlation_matrix(validation_analysis)

        save_result(
            correlation,
            args.output_dir / "correlation_matrix.csv",
            index=True,
        )

        print("\n[상관계수]")
        print(correlation)

        # -------------------------------------------------
        # 8. Welch's t-test
        # -------------------------------------------------

        ttest_results = run_welch_ttests(validation_analysis)

        save_result(
            ttest_results,
            args.output_dir / "welch_ttest_results.csv",
        )

        print("\n[Welch's t-test]")
        print(ttest_results.to_string(index=False))

        # -------------------------------------------------
        # 9. 거리 통제 다변량 회귀 / Partial F-test
        # -------------------------------------------------

        regression_result = run_distance_adjusted_regression(validation_analysis)

        save_result(
            regression_result,
            args.output_dir / "distance_adjusted_regression.csv",
        )

        print("\n[거리 통제 다변량 회귀 / Partial F-test]")

        print(regression_result.to_string(index=False))

        print("\n통계 분석 결과 저장 완료:")

        print(args.output_dir)

        # -------------------------------------------------
        # 10. RatecodeID == 1 민감도 분석
        # -------------------------------------------------

        standard_rate_analysis = filter_standard_rate(validation_analysis)

        print("\n[RatecodeID == 1 민감도 분석]")
        print(f"전체 Validation 분석 표본: " f"{len(validation_analysis):,}행")
        print(f"Standard rate 표본: " f"{len(standard_rate_analysis):,}행")
        print(
            f"Standard rate 비율: "
            f"{len(standard_rate_analysis) / len(validation_analysis):.2%}"
        )

        standard_descriptive = make_descriptive_statistics(standard_rate_analysis)

        save_result(
            standard_descriptive,
            args.output_dir / "standard_rate_descriptive_statistics.csv",
            index=True,
        )
        standard_group_counts = standard_rate_analysis["commute_group"].value_counts()

        print("\n[Standard rate 그룹별 표본 수]")
        print(standard_group_counts)

        print("\n[Standard rate - 기술통계]")
        print(standard_descriptive)

        standard_ttest_results = run_welch_ttests(standard_rate_analysis)

        save_result(
            standard_ttest_results,
            args.output_dir / "standard_rate_welch_ttest_results.csv",
        )

        print("\n[Standard rate - Welch's t-test]")
        print(standard_ttest_results.to_string(index=False))

        standard_regression_result = run_distance_adjusted_regression(
            standard_rate_analysis
        )

        save_result(
            standard_regression_result,
            args.output_dir / "standard_rate_distance_adjusted_regression.csv",
        )

        print("\n[Standard rate - " "거리 통제 다변량 회귀 / Partial F-test]")

        print(standard_regression_result.to_string(index=False))

        return 0

    except (
        FileNotFoundError,
        ValueError,
        KeyError,
    ) as exc:
        print(f"\n[오류] {exc}")

        return 1


if __name__ == "__main__":
    raise SystemExit(main())
