"""
작성자: 임동건
작성일: 2026.08.09
파일명: run_all.py

NYC Yellow Taxi 전체 분석 파이프라인 자동 실행

원본 데이터가 data/raw/에 존재한다는 전제에서
전처리 → 통계분석 → 시각화 → 머신러닝 → report.md 생성을 순차 실행한다.

어느 단계에서든 실패하면 즉시 중단하여 뒤 단계가 오래된 산출물을 사용하지 않도록 한다.

변경사항 내역
2026-08-09(최지윤):
- 전체 실행 파이프라인의 기본 입력 경로를 공통 상수로 교체
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from time import perf_counter

try:
    from src.project_paths import DEFAULT_RAW_DATA
except ModuleNotFoundError:  # 직접 스크립트로 실행할 때
    from project_paths import DEFAULT_RAW_DATA

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_RAW_DATA = PROJECT_ROOT / DEFAULT_RAW_DATA
CLEANED_DATA = PROJECT_ROOT / "data/processed/yellow_taxi_cleaned.parquet"
DATA_QUALITY_REPORT = PROJECT_ROOT / "reports/generated/data_quality_report.md"
STATISTICS_DIR = PROJECT_ROOT / "reports/generated/statistics"
VISUALIZATION_DIR = PROJECT_ROOT / "reports/generated/visualizations"
ML_DIR = PROJECT_ROOT / "reports/generated/ml"
FINAL_REPORT = PROJECT_ROOT / "report.md"


def display_path(path: Path) -> str:
    """
    절대경로를 프로젝트 폴더명을 포함한 상대경로 형태로 표시
    """

    path = path.resolve()

    try:
        relative = path.relative_to(PROJECT_ROOT.parent)
        return f".\\{relative}"
    except ValueError:
        return str(path)


# =========================================================
# 인수
# =========================================================


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "NYC Yellow Taxi 전처리·통계·시각화·ML·report.md " "전체 자동 실행"
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_RAW_DATA,
        help=(
            "원본 Taxi Parquet/CSV 경로 "
            f"(기본값: {DEFAULT_RAW_DATA.relative_to(PROJECT_ROOT)})"
        ),
    )
    return parser.parse_args()


def project_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


# =========================================================
# 실행 및 검증
# =========================================================


def verify_outputs(paths: list[Path], label: str) -> None:
    missing = [path for path in paths if not path.is_file()]
    if missing:
        missing_text = "\n".join(f"- {path}" for path in missing)
        raise FileNotFoundError(
            f"[{label}] 실행은 끝났지만 필요한 산출물이 없습니다.\n{missing_text}"
        )


def run_script(
    label: str,
    script: str,
    *args: str,
    expected_outputs: list[Path] | None = None,
) -> float:
    script_path = PROJECT_ROOT / script

    if not script_path.is_file():
        raise FileNotFoundError(f"실행 스크립트를 찾을 수 없습니다: {script_path}")

    command = [
        sys.executable,
        str(script_path),
        *args,
    ]

    print()
    print("=" * 70)
    print(f"[{label}]")
    print("=" * 70)

    started = perf_counter()

    subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=True,
    )

    elapsed = perf_counter() - started

    if expected_outputs:
        verify_outputs(expected_outputs, label)

    print(f"[{label}] 완료: {elapsed:.2f}초")
    return elapsed


# =========================================================
# Main
# =========================================================


def main() -> int:
    args = parse_args()
    raw_data = project_path(args.input)

    if not raw_data.is_file():
        print("[오류] 원본 데이터 파일을 찾을 수 없습니다.")
        print(f"필요한 파일: {display_path(raw_data)}")
        return 1

    # 이전 report.md가 남아 있으면 전체 실행 실패 시 최신 결과로 오해할 수 있으므로 제거한다.
    FINAL_REPORT.unlink(missing_ok=True)

    timings: list[tuple[str, float]] = []

    try:
        timings.append(
            (
                "전처리",
                run_script(
                    "1/5 데이터 전처리 및 품질 검증",
                    "src/prepare_data.py",
                    str(raw_data),
                    "--output",
                    str(CLEANED_DATA),
                    "--report",
                    str(DATA_QUALITY_REPORT),
                    expected_outputs=[CLEANED_DATA, DATA_QUALITY_REPORT],
                ),
            )
        )

        timings.append(
            (
                "통계분석",
                run_script(
                    "2/5 통계 분석",
                    "src/statistical_analysis.py",
                    "--input",
                    str(CLEANED_DATA),
                    "--output-dir",
                    str(STATISTICS_DIR),
                    expected_outputs=[
                        STATISTICS_DIR / "split_dates.csv",
                        STATISTICS_DIR / "hourly_demand_profile.csv",
                        STATISTICS_DIR / "descriptive_statistics.csv",
                        STATISTICS_DIR / "rush_period_descriptive_statistics.csv",
                        STATISTICS_DIR / "correlation_matrix.csv",
                        STATISTICS_DIR / "welch_ttest_results.csv",
                        STATISTICS_DIR / "distance_adjusted_regression.csv",
                        STATISTICS_DIR / "rush_period_distance_adjusted_regression.csv",
                    ],
                ),
            )
        )

        timings.append(
            (
                "시각화",
                run_script(
                    "3/5 시각화",
                    "src/visualization.py",
                    "--input",
                    str(CLEANED_DATA),
                    "--output-dir",
                    str(VISUALIZATION_DIR),
                    expected_outputs=[
                        VISUALIZATION_DIR / "commute_duration_boxplot.png",
                        VISUALIZATION_DIR / "distance_duration_facet.png",
                        VISUALIZATION_DIR / "hourly_duration_fare_trend.html",
                        VISUALIZATION_DIR / "distance_fare_scatter.html",
                    ],
                ),
            )
        )

        timings.append(
            (
                "머신러닝",
                run_script(
                    "4/5 머신러닝",
                    "src/ml.pipeline.py",
                    expected_outputs=[
                        ML_DIR / "model_results.csv",
                        PROJECT_ROOT / "best_model_trip_duration_min.pkl",
                    ],
                ),
            )
        )

        timings.append(
            (
                "보고서",
                run_script(
                    "5/5 최종 report.md 생성",
                    "src/generate_report.py",
                    "--data-quality-report",
                    str(DATA_QUALITY_REPORT),
                    "--statistics-dir",
                    str(STATISTICS_DIR),
                    "--visualization-dir",
                    str(VISUALIZATION_DIR),
                    "--ml-dir",
                    str(ML_DIR),
                    "--output",
                    str(FINAL_REPORT),
                    expected_outputs=[FINAL_REPORT],
                ),
            )
        )

    except subprocess.CalledProcessError as error:
        print()
        print("=" * 70)
        print("[실패] 전체 파이프라인이 중단되었습니다.")
        print(f"실패: {error.cmd}")
        print(f"종료 코드: {error.returncode}")
        print("뒤 단계는 실행하지 않았습니다.")
        print("=" * 70)
        return 1

    except FileNotFoundError as error:
        print()
        print("=" * 70)
        print("[실패] 필요한 파일 또는 산출물을 확인할 수 없습니다.")
        print(error)
        print("=" * 70)
        return 1

    total_seconds = sum(seconds for _, seconds in timings)

    print()
    print("=" * 70)
    print("전체 분석 파이프라인 실행 완료")
    print("=" * 70)

    for label, seconds in timings:
        print(f"- {label}: {seconds:.2f}초")

    print(f"- 전체: {total_seconds:.2f}초")
    print()
    print(f"정제 데이터: {display_path(CLEANED_DATA)}")
    print(f"품질 보고서: {display_path(DATA_QUALITY_REPORT)}")
    print(f"통계 결과: {display_path(STATISTICS_DIR)}")
    print(f"시각화 결과: {display_path(VISUALIZATION_DIR)}")
    print(f"ML 결과: {display_path(ML_DIR / 'model_results.csv')}")
    print(f"최종 보고서: {display_path(FINAL_REPORT)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
