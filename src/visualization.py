"""
작성자: 강건호
작성일: 2026-08-09
파일명: visualization.py

NYC Yellow Taxi 출퇴근 시간대가 이동시간·요금에 미치는 영향 시각화

- prepare_data.py가 생성한 정제 데이터의 rush_period, weekday_comparison_group 등
  파생 변수를 그대로 재사용한다 (재계산하지 않음).
- 통계 파트(statistical_analysis.py)와 동일한 분석 대상 월(2026년 5월), 공휴일 제외,
  이상치 후보 제외 기준을 적용해 시각화와 통계 검정의 결론이 어긋나지 않게 한다.
- Seaborn 정적 차트 2종(그룹 비교 boxplot, 패널 산점도)과 Plotly 인터랙티브 차트 2종
  (24시간 추이, 그룹별 산점도)을 생성한다.

변경사항 내역
2026-08-09:
- Seaborn boxplot(그룹 비교) + Plotly 24시간 추이(그룹 비교) 초안 작성
- 공통 테마(whitegrid, 공유 색상 팔레트)로 정리하고 Seaborn 패널 산점도,
  Plotly 그룹별 산점도(상관관계) 2종 추가
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import pandas as pd
import plotly.graph_objects as go
import seaborn as sns

logger = logging.getLogger(__name__)

DEFAULT_INPUT = Path("data/processed/yellow_taxi_cleaned.parquet")
DEFAULT_OUTPUT_DIR = Path("reports/generated/visualizations")

ANALYSIS_COLUMNS = [
    "tpep_pickup_datetime",
    "pickup_hour",
    "is_weekday",
    "rush_period",
    "trip_distance",
    "trip_duration_min",
    "fare_amount",
    "is_long_trip_candidate",
    "is_large_distance_candidate",
    "is_large_fare_candidate",
]

# 통계 파트(statistical_analysis.py)와 동일한 분석 대상 월·공휴일 기준.
# 그룹 정의(rush_period)가 어긋나면 발표에서 시각화와 통계 결론이 앞뒤가 안 맞으므로 맞춘다.
ANALYSIS_MONTH_START = pd.Timestamp("2026-05-01")
ANALYSIS_MONTH_END = pd.Timestamp("2026-06-01")
HOLIDAYS = {pd.Timestamp("2026-05-25")}

# prepare_data.py가 보존한 이상치 후보 플래그 중 이동시간·거리·요금 분석과 관련된 3종만 제외한다.
# is_invalid_passenger_candidate는 승객 수 이상치라 이번 분석 대상과 무관해 제외하지 않는다.
OUTLIER_CANDIDATE_COLUMNS = [
    "is_long_trip_candidate",
    "is_large_distance_candidate",
    "is_large_fare_candidate",
]

RUSH_PERIOD_ORDER = ["morning_rush", "evening_rush", "weekday_non_rush"]
RUSH_PERIOD_TITLES = {
    "morning_rush": "출근 러시 (06-10시)",
    "evening_rush": "퇴근 러시 (16-20시)",
    "weekday_non_rush": "평일 비출퇴근",
}
RUSH_PERIOD_TICK_LABELS = {
    "morning_rush": "출근 러시\n(06-10시)",
    "evening_rush": "퇴근 러시\n(16-20시)",
    "weekday_non_rush": "평일 비출퇴근",
}
RUSH_PERIOD_MARKERS = {
    "morning_rush": "o",
    "evening_rush": "X",
    "weekday_non_rush": "s",
}

# Seaborn·Plotly가 공유하는 색상 팔레트 (색약 대응 Okabe-Ito 계열)
CATEGORY_COLORS = {
    "morning_rush": "#E69F00",
    "evening_rush": "#D55E00",
    "weekday_non_rush": "#0072B2",
}
RUSH_SHADING_COLOR = "#D55E00"

# Windows 환경에서 Pretendard가 설치돼 있으면 우선 사용하고, 없으면 Malgun Gothic으로 대체한다.
FONT_PRIORITY = ["Pretendard", "Malgun Gothic", "NanumGothic", "AppleGothic", "DejaVu Sans"]

FIGURE_DPI = 150
DURATION_AXIS_LIMIT_MIN = 55
SCATTER_SAMPLE_SIZE = 1200
RANDOM_SEED = 42
AXIS_QUANTILE = 0.99


def configure_plot_style() -> str:
    """논문 도판 수준의 공통 테마(배경·격자·폰트)를 matplotlib/Seaborn에 적용한다."""
    sns.set_theme(style="whitegrid", context="notebook", font_scale=1.05)
    available = {font.name for font in fm.fontManager.ttflist}
    chosen = next((name for name in FONT_PRIORITY if name in available), "DejaVu Sans")
    plt.rcParams["font.family"] = chosen
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["axes.edgecolor"] = "#333333"
    plt.rcParams["grid.color"] = "#dddddd"
    plt.rcParams["grid.linewidth"] = 0.6
    logger.info("한글 폰트 적용: %s", chosen)
    return chosen


def load_cleaned_data(path: Path) -> pd.DataFrame:
    """prepare_data.py가 생성한 정제 Parquet에서 시각화에 필요한 컬럼만 읽는다."""
    if not path.is_file():
        raise FileNotFoundError(
            f"정제 데이터 파일을 찾을 수 없습니다: {path}. "
            "먼저 'python src/prepare_data.py data/raw/yellow_tripdata_2026-05.parquet'를 "
            "실행해 데이터를 준비하세요."
        )
    df = pd.read_parquet(path, columns=ANALYSIS_COLUMNS)
    logger.info("정제 데이터 로딩 완료: %s행", f"{len(df):,}")
    return df


def filter_analysis_scope(df: pd.DataFrame) -> pd.DataFrame:
    """통계 파트와 동일한 분석 범위(2026년 5월, 공휴일 제외, 이상치 후보 제외)로 제한한다."""
    before = len(df)
    scoped = df.loc[
        (df["tpep_pickup_datetime"] >= ANALYSIS_MONTH_START)
        & (df["tpep_pickup_datetime"] < ANALYSIS_MONTH_END)
    ].copy()
    logger.info("분석 대상 월(2026-05) 필터링: %s행 -> %s행", f"{before:,}", f"{len(scoped):,}")

    pickup_date = scoped["tpep_pickup_datetime"].dt.normalize()
    scoped = scoped.loc[~pickup_date.isin(HOLIDAYS)].copy()
    logger.info("공휴일 제외 후: %s행", f"{len(scoped):,}")

    candidate_mask = scoped[OUTLIER_CANDIDATE_COLUMNS].fillna(False).astype(bool).any(axis=1)
    scoped = scoped.loc[~candidate_mask].copy()
    logger.info(
        "이상치 후보 제외 후: %s행 (제외 %s행)",
        f"{len(scoped):,}",
        f"{int(candidate_mask.sum()):,}",
    )
    return scoped


def sample_by_group(
    df: pd.DataFrame, group_column: str, groups: list[str], sample_size: int, seed: int
) -> pd.DataFrame:
    """산점도 과밀을 막기 위해 그룹별로 동일한 개수만큼 표본을 추출한다."""
    parts = []
    for group in groups:
        group_df = df.loc[df[group_column] == group]
        take = min(sample_size, len(group_df))
        parts.append(group_df.sample(n=take, random_state=seed))
    return pd.concat(parts, ignore_index=True)


def quantile_limit(series: pd.Series, quantile: float) -> float:
    """축 상한을 분포 분위수로 정해 극단값 몇 개로 그래프가 눌리지 않게 한다."""
    return float(series.quantile(quantile))


def make_duration_boxplot(df: pd.DataFrame, output_path: Path) -> Path:
    """출퇴근 시간대 3그룹(출근 러시/퇴근 러시/평일 비출퇴근)의 이동시간 분포를 비교한다."""
    subset = df.loc[df["rush_period"].isin(RUSH_PERIOD_ORDER)]

    fig, ax = plt.subplots(figsize=(8, 6))
    sns.boxplot(
        data=subset,
        x="rush_period",
        y="trip_duration_min",
        hue="rush_period",
        order=RUSH_PERIOD_ORDER,
        hue_order=RUSH_PERIOD_ORDER,
        palette=CATEGORY_COLORS,
        showfliers=False,
        width=0.55,
        linewidth=1.3,
        legend=False,
        ax=ax,
    )

    medians = subset.groupby("rush_period")["trip_duration_min"].median()
    for index, period in enumerate(RUSH_PERIOD_ORDER):
        median_value = medians.loc[period]
        ax.text(
            index,
            median_value,
            f"{median_value:.1f}분",
            ha="center",
            va="bottom",
            fontsize=11,
            fontweight="bold",
            color="#222222",
        )

    ax.set_title(
        "출퇴근 시간대별 이동시간 분포\n(2026년 5월, 평일)",
        fontsize=15,
        fontweight="bold",
        pad=14,
    )
    ax.set_xlabel("시간대 구분", fontsize=12, labelpad=8)
    ax.set_ylabel("이동시간 (분)", fontsize=12, labelpad=8)
    ax.set_xticks(range(len(RUSH_PERIOD_ORDER)))
    ax.set_xticklabels([RUSH_PERIOD_TICK_LABELS[period] for period in RUSH_PERIOD_ORDER], fontsize=11)
    ax.tick_params(axis="y", labelsize=10)
    ax.set_ylim(0, DURATION_AXIS_LIMIT_MIN)
    ax.yaxis.grid(True, alpha=0.35, linewidth=0.6)
    ax.xaxis.grid(False)
    sns.despine(ax=ax)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)
    logger.info("Seaborn boxplot 저장 완료: %s", output_path)
    return output_path


def make_distance_duration_facet(df: pd.DataFrame, output_path: Path) -> Path:
    """시간대 구간별 이동거리 대비 이동시간 관계를 패널로 나눠 혼잡 효과를 비교한다."""
    sample = sample_by_group(
        df, "rush_period", RUSH_PERIOD_ORDER, SCATTER_SAMPLE_SIZE, RANDOM_SEED
    )
    x_limit = quantile_limit(sample["trip_distance"], AXIS_QUANTILE)
    y_limit = quantile_limit(sample["trip_duration_min"], AXIS_QUANTILE)

    grid = sns.relplot(
        data=sample,
        x="trip_distance",
        y="trip_duration_min",
        col="rush_period",
        col_order=RUSH_PERIOD_ORDER,
        hue="rush_period",
        hue_order=RUSH_PERIOD_ORDER,
        style="rush_period",
        style_order=RUSH_PERIOD_ORDER,
        markers=RUSH_PERIOD_MARKERS,
        palette=CATEGORY_COLORS,
        s=55,
        alpha=0.75,
        edgecolor="white",
        linewidth=0.4,
        legend=False,
        height=4.2,
        aspect=1.05,
        facet_kws={"despine": True},
    )

    grid.set(xlim=(0, x_limit), ylim=(0, y_limit))
    grid.set_axis_labels("이동 거리 (마일)", "이동시간 (분)", fontsize=12)
    for axis, period in zip(grid.axes.flat, RUSH_PERIOD_ORDER):
        axis.set_title(RUSH_PERIOD_TITLES[period], fontsize=13, fontweight="bold")
        axis.yaxis.grid(True, alpha=0.35, linewidth=0.6)
        axis.xaxis.grid(False)
        axis.tick_params(labelsize=10)
    grid.figure.suptitle(
        "시간대 구간별 이동거리-이동시간 관계 (2026년 5월, 평일)",
        fontsize=15,
        fontweight="bold",
        y=1.04,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    grid.savefig(output_path, dpi=FIGURE_DPI, bbox_inches="tight")
    plt.close(grid.figure)
    logger.info("Seaborn 패널 산점도 저장 완료: %s", output_path)
    return output_path


def make_hourly_interactive_chart(df: pd.DataFrame, output_path: Path) -> Path:
    """평일 24시간 x축에 평균 이동시간·평균 요금을 함께 표시하고 출퇴근 구간을 강조한다."""
    weekday_df = df.loc[df["is_weekday"]]
    hourly = (
        weekday_df.groupby("pickup_hour")
        .agg(avg_duration=("trip_duration_min", "mean"), avg_fare=("fare_amount", "mean"))
        .reindex(range(24))
        .rename_axis("hour")
        .reset_index()
    )

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=hourly["hour"],
            y=hourly["avg_duration"],
            name="평균 이동시간 (분)",
            mode="lines+markers",
            line={"color": CATEGORY_COLORS["evening_rush"], "width": 3, "shape": "spline"},
            marker={"size": 8, "line": {"width": 1, "color": "white"}},
            hovertemplate="%{x}시<br>평균 이동시간: %{y:.1f}분<extra></extra>",
            yaxis="y",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=hourly["hour"],
            y=hourly["avg_fare"],
            name="평균 요금 ($)",
            mode="lines+markers",
            line={
                "color": CATEGORY_COLORS["weekday_non_rush"],
                "width": 3,
                "dash": "dot",
                "shape": "spline",
            },
            marker={"size": 8, "symbol": "diamond", "line": {"width": 1, "color": "white"}},
            hovertemplate="%{x}시<br>평균 요금: $%{y:.2f}<extra></extra>",
            yaxis="y2",
        )
    )

    fig.add_vrect(
        x0=6, x1=10, fillcolor=RUSH_SHADING_COLOR, opacity=0.12, line_width=0,
        annotation_text="출근 러시", annotation_position="top left",
    )
    fig.add_vrect(
        x0=16, x1=20, fillcolor=RUSH_SHADING_COLOR, opacity=0.12, line_width=0,
        annotation_text="퇴근 러시", annotation_position="top left",
    )

    fig.update_layout(
        title={"text": "시간대별 평균 이동시간·요금 추이 (2026년 5월, 평일)", "x": 0.02},
        xaxis={"title": "승차 시각 (0~23시)", "tickmode": "linear", "dtick": 1},
        yaxis={"title": "평균 이동시간 (분)", "side": "left"},
        yaxis2={"title": "평균 요금 ($)", "overlaying": "y", "side": "right"},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
        template="plotly_white",
        font={"family": "Malgun Gothic, Pretendard, sans-serif", "size": 13},
        hovermode="x unified",
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(output_path)
    logger.info("Plotly 추이 차트 저장 완료: %s", output_path)
    return output_path


def make_distance_fare_scatter(df: pd.DataFrame, output_path: Path) -> Path:
    """이동거리 대비 요금 관계를 시간대 구간별 색상으로 구분해 상호작용 가능하게 표시한다."""
    sample = sample_by_group(
        df, "rush_period", RUSH_PERIOD_ORDER, SCATTER_SAMPLE_SIZE, RANDOM_SEED
    )
    x_limit = quantile_limit(sample["trip_distance"], AXIS_QUANTILE)
    y_limit = quantile_limit(sample["fare_amount"], AXIS_QUANTILE)

    fig = go.Figure()
    for period in RUSH_PERIOD_ORDER:
        group = sample.loc[sample["rush_period"] == period]
        fig.add_trace(
            go.Scattergl(
                x=group["trip_distance"],
                y=group["fare_amount"],
                name=RUSH_PERIOD_TITLES[period],
                mode="markers",
                marker={
                    "color": CATEGORY_COLORS[period],
                    "size": 6,
                    "opacity": 0.65,
                    "line": {"width": 0.5, "color": "white"},
                },
                hovertemplate=(
                    RUSH_PERIOD_TITLES[period]
                    + "<br>이동 거리: %{x:.2f}마일<br>요금: $%{y:.2f}<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        title={"text": "시간대 구간별 이동거리-요금 관계 (2026년 5월, 평일)", "x": 0.02},
        xaxis={"title": "이동 거리 (마일)", "range": [0, x_limit]},
        yaxis={"title": "미터 운임 ($)", "range": [0, y_limit]},
        legend={"title": {"text": "시간대 구분"}},
        template="plotly_white",
        font={"family": "Malgun Gothic, Pretendard, sans-serif", "size": 13},
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(output_path)
    logger.info("Plotly 산점도 저장 완료: %s", output_path)
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NYC Yellow Taxi 출퇴근 시간대 시각화")
    parser.add_argument(
        "--input", type=Path, default=DEFAULT_INPUT,
        help="prepare_data.py가 생성한 정제 Parquet 경로",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
        help="차트 저장 디렉터리",
    )
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    args = parse_args()

    try:
        configure_plot_style()
        raw = load_cleaned_data(args.input)
        scoped = filter_analysis_scope(raw)

        output_paths = [
            make_duration_boxplot(scoped, args.output_dir / "commute_duration_boxplot.png"),
            make_distance_duration_facet(scoped, args.output_dir / "distance_duration_facet.png"),
            make_hourly_interactive_chart(scoped, args.output_dir / "hourly_duration_fare_trend.html"),
            make_distance_fare_scatter(scoped, args.output_dir / "distance_fare_scatter.html"),
        ]

        logger.info("시각화 완료: %s", ", ".join(str(path) for path in output_paths))
        return 0
    except (FileNotFoundError, ValueError) as error:
        logger.error("오류: %s", error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
