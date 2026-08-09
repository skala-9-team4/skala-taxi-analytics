"""
작성자: 임동건
작성일: 2026.08.09
파일명: generate_report.py

NYC Yellow Taxi 분석 결과 자동 보고서 생성

각 분석 단계에서 생성한 CSV와 시각화 파일을 읽어
프로젝트 루트의 report.md를 자동 생성한다.
"""

from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

# =========================================================
# 기본 경로
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_DATA_QUALITY_REPORT = PROJECT_ROOT / "reports/generated/data_quality_report.md"
DEFAULT_STATISTICS_DIR = PROJECT_ROOT / "reports/generated/statistics"
DEFAULT_VISUALIZATION_DIR = PROJECT_ROOT / "reports/generated/visualizations"
DEFAULT_ML_DIR = PROJECT_ROOT / "reports/generated/ml"
DEFAULT_OUTPUT = PROJECT_ROOT / "report.md"


VARIABLE_LABELS = {
    "trip_distance": "이동거리 (mile)",
    "trip_duration_min": "이동시간 (분)",
    "fare_amount": "미터 운임 ($)",
    "total_amount": "총 결제금액 ($)",
    "extra": "추가요금 extra ($)",
}

GROUP_LABELS = {
    "weekday_rush": "평일 출퇴근",
    "weekday_non_rush": "평일 비출퇴근",
    "morning_rush": "오전 출근 (06-10시)",
    "evening_rush": "오후 퇴근 (16-20시)",
}


# =========================================================
# 공통 유틸리티
# =========================================================


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="NYC Yellow Taxi 최종 report.md 자동 생성"
    )
    parser.add_argument(
        "--data-quality-report",
        type=Path,
        default=DEFAULT_DATA_QUALITY_REPORT,
        help="prepare_data.py가 생성한 데이터 품질 보고서",
    )
    parser.add_argument(
        "--statistics-dir",
        type=Path,
        default=DEFAULT_STATISTICS_DIR,
        help="statistical_analysis.py 결과 디렉터리",
    )
    parser.add_argument(
        "--visualization-dir",
        type=Path,
        default=DEFAULT_VISUALIZATION_DIR,
        help="visualization.py 결과 디렉터리",
    )
    parser.add_argument(
        "--ml-dir",
        type=Path,
        default=DEFAULT_ML_DIR,
        help="머신러닝 성능 결과 디렉터리",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="최종 Markdown 보고서 경로",
    )
    return parser.parse_args()


def project_path(path: Path) -> Path:
    """상대경로는 프로젝트 루트 기준으로 해석한다."""
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def require_file(path: Path) -> Path:
    path = project_path(path)
    if not path.is_file():
        raise FileNotFoundError(f"필요한 결과 파일을 찾을 수 없습니다: {path}")
    return path


def require_columns(df: pd.DataFrame, columns: set[str], source: Path) -> None:
    missing = columns - set(df.columns)
    if missing:
        raise KeyError(
            f"{source}에 필요한 컬럼이 없습니다: {', '.join(sorted(missing))}"
        )


def as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def format_number(value: object, digits: int = 4) -> str:
    return f"{float(value):.{digits}f}"


def format_p_value(value: object) -> str:
    number = float(value)
    if number < 0.001:
        return "< 0.001"
    return f"{number:.4f}"


def markdown_path(path: Path) -> str:
    """report.md에서 사용할 프로젝트 루트 기준 경로를 만든다."""
    resolved = project_path(path).resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


# =========================================================
# data_quality_report.md 처리
# =========================================================


def load_data_quality_report(path: Path) -> str:
    return require_file(path).read_text(encoding="utf-8")


def extract_quality_preamble(markdown: str) -> str:
    """첫 번째 ## 섹션 이전의 원본 경로·크기·검증 결론을 가져온다."""
    lines = markdown.splitlines()
    collected: list[str] = []

    for line in lines[1:]:  # 첫 # 제목 제외
        if line.startswith("## "):
            break
        if line.strip():
            collected.append(line)

    return "\n".join(collected).strip()


def extract_markdown_section(markdown: str, section_title: str) -> str:
    """특정 ## 섹션부터 다음 ## 섹션 전까지 내용을 추출한다."""
    pattern = re.compile(
        rf"^## {re.escape(section_title)}\s*$\n(.*?)(?=^## |\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(markdown)
    if match is None:
        return ""
    return match.group(1).strip()


def make_data_quality_section(markdown: str) -> str:
    """
    상세 품질 보고서에서 최종 보고서에 필요한 핵심 부분만 가져온다.

    Pandas/Polars의 전체 EDA와 전처리 단계의 출퇴근 기초통계는
    최종 분석 표본과 혼동될 수 있어 여기서는 제외한다.
    """
    preamble = extract_quality_preamble(markdown)

    section_titles = [
        "로딩 시간·메모리 비교",
        "Pandas와 Polars의 원본 EDA 결과 비교",
        "분석 기간 점검",
        "Pandas와 Polars의 단계별 정제 결과 비교",
        "요금 지표의 의미",
        "생성된 파생 변수",
        "출퇴근 시간대 분류",
        "보존된 이상치 후보",
        "정제 및 EDA 실행 시간 비교",
        "검증 항목 및 정제 결과 표본 일치 여부",
    ]

    parts: list[str] = []

    if preamble:
        parts.append("### 전처리 결과 요약\n\n" + preamble)

    for title in section_titles:
        content = extract_markdown_section(markdown, title)
        if not content:
            continue

        parts.append(f"### {title}\n\n{content}")

    if not parts:
        raise ValueError("data_quality_report.md에서 포함할 섹션을 찾지 못했습니다.")

    return "\n\n".join(parts)


# =========================================================
# 분석 결과 로딩
# =========================================================


def load_descriptive(path: Path) -> pd.DataFrame:
    path = require_file(path)
    return pd.read_csv(path, header=[0, 1], index_col=0)


def load_standard_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(require_file(path))


def load_correlation(path: Path) -> pd.DataFrame:
    path = require_file(path)
    return pd.read_csv(path, index_col=0)


# =========================================================
# Markdown 표 생성
# =========================================================


def descriptive_mean_table(
    descriptive: pd.DataFrame,
    groups: list[str],
) -> str:
    rows: list[dict[str, object]] = []

    for group in groups:
        if group not in descriptive.index:
            continue

        rows.append(
            {
                "구분": GROUP_LABELS.get(group, group),
                "표본 수": int(
                    float(descriptive.loc[group, ("trip_duration_min", "count")])
                ),
                "평균 이동거리": format_number(
                    descriptive.loc[group, ("trip_distance", "mean")], 3
                ),
                "평균 이동시간": format_number(
                    descriptive.loc[group, ("trip_duration_min", "mean")], 3
                ),
                "평균 미터 운임": format_number(
                    descriptive.loc[group, ("fare_amount", "mean")], 2
                ),
                "평균 총금액": format_number(
                    descriptive.loc[group, ("total_amount", "mean")], 2
                ),
            }
        )

    if not rows:
        raise ValueError("기술통계 CSV에서 필요한 그룹을 찾지 못했습니다.")

    return pd.DataFrame(rows).to_markdown(index=False)


def make_correlation_table(correlation: pd.DataFrame) -> str:
    display = correlation.rename(
        index=VARIABLE_LABELS,
        columns=VARIABLE_LABELS,
    ).copy()
    return display.to_markdown(floatfmt=".4f")


def make_ttest_table(ttest: pd.DataFrame) -> str:
    source = DEFAULT_STATISTICS_DIR / "welch_ttest_results.csv"
    require_columns(
        ttest,
        {
            "variable",
            "commute_mean",
            "non_commute_mean",
            "mean_difference",
            "t_statistic",
            "p_value",
            "reject_h0",
        },
        source,
    )

    rows: list[dict[str, object]] = []
    for _, row in ttest.iterrows():
        rows.append(
            {
                "변수": VARIABLE_LABELS.get(row["variable"], row["variable"]),
                "출퇴근 평균": format_number(row["commute_mean"], 4),
                "비출퇴근 평균": format_number(row["non_commute_mean"], 4),
                "평균 차이": format_number(row["mean_difference"], 4),
                "t": format_number(row["t_statistic"], 3),
                "p-value": format_p_value(row["p_value"]),
                "판정": "유의" if as_bool(row["reject_h0"]) else "유의하지 않음",
            }
        )

    return pd.DataFrame(rows).to_markdown(index=False)


def make_regression_table(regression: pd.DataFrame) -> str:
    row = regression.iloc[0]
    table = pd.DataFrame(
        [
            {
                "표본 수": int(row["n"]),
                "거리 계수": format_number(row["distance_coefficient"], 4),
                "출퇴근 계수(분)": format_number(row["rush_coefficient"], 4),
                "95% CI(분)": (
                    f"[{float(row['rush_ci_low']):.4f}, "
                    f"{float(row['rush_ci_high']):.4f}]"
                ),
                "Partial F": format_number(row["partial_f_statistic"], 3),
                "p-value": format_p_value(row["p_value"]),
                "Reduced R²": format_number(row["reduced_r2"], 6),
                "Full R²": format_number(row["full_r2"], 6),
                "ΔR²": format_number(row["delta_r2"], 6),
            }
        ]
    )
    return table.to_markdown(index=False)


def make_period_regression_table(regression: pd.DataFrame) -> str:
    row = regression.iloc[0]
    table = pd.DataFrame(
        [
            {
                "기준 집단": GROUP_LABELS.get(
                    row["reference_group"], row["reference_group"]
                ),
                "오전 계수(분)": format_number(row["morning_coefficient"], 4),
                "오전 p-value": format_p_value(row["morning_p_value"]),
                "오후 계수(분)": format_number(row["evening_coefficient"], 4),
                "오후 p-value": format_p_value(row["evening_p_value"]),
                "Joint Partial F": format_number(row["partial_f_statistic"], 3),
                "Joint p-value": format_p_value(row["partial_f_p_value"]),
                "ΔR²": format_number(row["delta_r2"], 6),
            }
        ]
    )
    return table.to_markdown(index=False)


def make_ml_table(ml_results: pd.DataFrame) -> str:
    require_columns(
        ml_results,
        {"model", "R2", "RMSE", "MAE", "is_best"},
        DEFAULT_ML_DIR / "model_results.csv",
    )

    rows: list[dict[str, object]] = []
    for _, row in ml_results.iterrows():
        rows.append(
            {
                "모델": row["model"],
                "R²": format_number(row["R2"], 4),
                "RMSE": format_number(row["RMSE"], 4),
                "MAE": format_number(row["MAE"], 4),
                "최적 모델": "✓" if as_bool(row["is_best"]) else "",
            }
        )

    return pd.DataFrame(rows).to_markdown(index=False)


# =========================================================
# 자동 해석 문장
# =========================================================


def get_ttest_row(ttest: pd.DataFrame, variable: str) -> pd.Series:
    matched = ttest.loc[ttest["variable"].eq(variable)]
    if matched.empty:
        raise ValueError(f"Welch t-test 결과에서 {variable}을 찾지 못했습니다.")
    return matched.iloc[0]


def find_model_row(ml_results: pd.DataFrame, prefix: str) -> pd.Series | None:
    matched = ml_results.loc[ml_results["model"].astype(str).str.startswith(prefix)]
    if matched.empty:
        return None
    return matched.iloc[0]


# =========================================================
# 최종 보고서 생성
# =========================================================


def generate_report(args: argparse.Namespace) -> str:
    statistics_dir = project_path(args.statistics_dir)
    visualization_dir = project_path(args.visualization_dir)
    ml_dir = project_path(args.ml_dir)

    quality_markdown = load_data_quality_report(args.data_quality_report)

    descriptive = load_descriptive(statistics_dir / "descriptive_statistics.csv")
    period_descriptive = load_descriptive(
        statistics_dir / "rush_period_descriptive_statistics.csv"
    )
    correlation = load_correlation(statistics_dir / "correlation_matrix.csv")
    ttest = load_standard_csv(statistics_dir / "welch_ttest_results.csv")
    regression = load_standard_csv(statistics_dir / "distance_adjusted_regression.csv")
    period_regression = load_standard_csv(
        statistics_dir / "rush_period_distance_adjusted_regression.csv"
    )
    ml_results = load_standard_csv(ml_dir / "model_results.csv")

    duration_boxplot = require_file(visualization_dir / "commute_duration_boxplot.png")
    distance_duration = require_file(visualization_dir / "distance_duration_facet.png")
    hourly_chart = require_file(visualization_dir / "hourly_duration_fare_trend.html")
    distance_fare = require_file(visualization_dir / "distance_fare_scatter.html")

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M %Z")

    return f"""# NYC Yellow Taxi 출퇴근 시간대 분석 보고서

> 생성 시각: {generated_at}

---

## 1. 프로젝트 개요

본 프로젝트는 **2026년 5월 NYC Yellow Taxi 데이터**를 이용하여 평일 출퇴근 시간대가
택시의 **이동시간과 요금에 어떤 차이를 보이는지** 확인하는 것을 목적으로 한다.

초기 탐색에서는 이동시간과 요금을 함께 분석하였다. 이후 요금은 이동거리 및 요금 구성요소와
강하게 연결되어 있어 시간대 자체의 차이로 단순 해석하기 어렵다고 판단하여,
후속 회귀분석과 머신러닝에서는 **`trip_duration_min`을 핵심 분석 대상으로 설정**하였다.
요금 분석 결과는 탐색 및 보조 해석으로 유지하였다.

---

## 2. 데이터 준비 및 품질 검증

{make_data_quality_section(quality_markdown)}

상세 dtype, 결측치, 전체 범주·코드 빈도 등은
[`data_quality_report.md`]({markdown_path(args.data_quality_report)})에서 확인할 수 있다.

---

## 3. 분석 설계

- 분석 대상 월: 2026년 5월 승차 데이터
- 출근 시간대: 평일 06:00 이상 10:00 미만
- 퇴근 시간대: 평일 16:00 이상 20:00 미만
- 평일 비출퇴근 시간대: 위 두 구간을 제외한 평일
- 2026-05-25 공휴일은 통계분석에서 제외
- Discovery / Validation은 날짜 단위로 분리
- 통계적 추론은 Validation의 평일 데이터에서 수행
- `is_long_trip_candidate`, `is_large_distance_candidate`, `is_large_fare_candidate`는
  Validation 분석에서 제외

---

## 4. 기술통계 및 상관분석

### 4.1 평일 출퇴근 / 비출퇴근 기술통계

{descriptive_mean_table(descriptive, ['weekday_rush', 'weekday_non_rush'])}

### 4.2 오전 / 오후 / 비출퇴근 기술통계

{descriptive_mean_table(period_descriptive, ['morning_rush', 'evening_rush', 'weekday_non_rush'])}

### 4.3 Pearson 상관계수

{make_correlation_table(correlation)}

요금 변수는 이동거리와 높은 관계를 보이며 `fare_amount`와 `total_amount`도 서로 매우 강하게 연결되어 있다.
따라서 요금의 단순 집단 차이는 시간대 자체의 효과로 해석하지 않고 보조 결과로 활용한다.

---

## 5. 시각화

### 5.1 출퇴근 시간대별 이동시간 분포

![출퇴근 시간대별 이동시간 분포]({markdown_path(duration_boxplot)})

### 5.2 시간대 구간별 이동거리-이동시간 관계

![시간대 구간별 이동거리-이동시간 관계]({markdown_path(distance_duration)})

### 5.3 시간대별 평균 이동시간·요금 추이

[인터랙티브 차트 열기]({markdown_path(hourly_chart)})

### 5.4 시간대 구간별 이동거리-요금 관계

[인터랙티브 산점도 열기]({markdown_path(distance_fare)})

데이터 전처리 단계에서 만든 `rush_period`과 `weekday_comparison_group`을 그대로 재사용하고,
분석 범위도 통계 부분과 동일하게 설정하였다. 

---

## 6. Welch 독립표본 t-test

{make_ttest_table(ttest)}

---

## 7. 이동거리 통제 회귀분석

단순 평균 비교에서는 출퇴근 시간대와 비출퇴근 시간대의 이동거리 구성이 다르다는 점을 통제할 수 없다.
따라서 `trip_duration_min ~ trip_distance`를 Reduced model로 두고,
출퇴근 여부 또는 오전·오후 시간대를 추가한 Full model과 비교하였다.

### 7.1 출퇴근 여부 추가

{make_regression_table(regression)}

### 7.2 오전 / 오후 세분화

{make_period_regression_table(period_regression)}

---

## 8. 머신러닝 이동시간 예측

본 머신러닝 파이프라인은 택시의 운행 조건(이동 거리, 출퇴근 시간대, 승/하차 위치)이 주었을 때,
해당 택시의 최종 이동시간을 예측하는 모델이다.
앞선 통계분석 결과를 바탕으로 변수를 선택하여 예측 성능과 해석력을 높이고자 하였다.

{make_ml_table(ml_results)}

---

## 9. 자동화 및 산출물

전체 자동화는 원본 데이터가 `data/raw/`에 존재한다는 전제에서 다음 순서로 수행한다.

```text
원본 Parquet
    ↓
prepare_data.py
    ↓
정제 Parquet + data_quality_report.md
    ↓
statistical_analysis.py
    ↓
통계 결과 CSV
    ↓
visualization.py
    ↓
PNG / HTML 시각화
    ↓
ml.pipeline.py
    ↓
모델 성능 CSV + 최적 모델
    ↓
generate_report.py
    ↓
report.md
```
"""


# =========================================================
# Main
# =========================================================


def main() -> int:
    args = parse_args()

    try:
        report = generate_report(args)
        output = project_path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report, encoding="utf-8")

        print("=" * 60)
        print("최종 Markdown 보고서 자동 생성 완료")
        print("=" * 60)
        print(output)
        return 0

    except (
        FileNotFoundError,
        KeyError,
        ValueError,
        IndexError,
    ) as error:
        print(f"[오류] report.md 생성 실패: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
