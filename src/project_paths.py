# 작성자: 최지윤
# 작성 목적: 프로젝트에서 공통으로 사용하는 경로를 관리
# 작성일: 2026-08-09
#
# 변경사항 내역
# 2026-08-09:
# - 분석에 사용하는 공통 기본 입력 데이터 경로 상수를 추가

from pathlib import Path

DEFAULT_RAW_DATA = Path("data/raw/yellow_tripdata_2026-05.parquet")
