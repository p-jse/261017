import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="서울 기온 변화 대시보드", page_icon="🌡️", layout="wide")

CSV_PATH = "seoul_temperature.csv"
DATE_COL = "날짜"
AVG_COL = "평균기온(℃)"
MIN_COL = "최저기온(℃)"
MAX_COL = "최고기온(℃)"
MISSING_YEARS = [1950, 1951, 1952, 1953]


@st.cache_data
def load_data(file_bytes=None):
    """CSV를 읽고 날짜 앞의 탭/공백을 제거한 뒤 연도별 자료를 만든다."""
    if file_bytes is None:
        df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")
    else:
        from io import BytesIO
        df = pd.read_csv(BytesIO(file_bytes), encoding="utf-8-sig")

    required = [DATE_COL, AVG_COL, MIN_COL, MAX_COL]
    missing_cols = [col for col in required if col not in df.columns]
    if missing_cols:
        raise ValueError(f"CSV에 필요한 컬럼이 없습니다: {', '.join(missing_cols)}")

    # 날짜 값 앞에 들어 있는 탭 문자(\t)와 앞뒤 공백을 제거
    df[DATE_COL] = pd.to_datetime(
        df[DATE_COL].astype(str).str.strip(), errors="coerce"
    )
    for col in [AVG_COL, MIN_COL, MAX_COL]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=[DATE_COL]).copy()
    df["연도"] = df[DATE_COL].dt.year.astype(int)

    # 연도별 통계. 측정값이 없는 연도는 자동으로 NaN이 된다.
    annual = (
        df.groupby("연도")
        .agg(
            평균기온=(AVG_COL, "mean"),
            최고기온=(MAX_COL, "max"),
            최저기온=(MIN_COL, "min"),
            관측일수=(AVG_COL, "count"),
        )
    )

    # 1950~1953년은 자료가 없거나 일부만 존재하므로 연간 대표값으로 사용하지 않는다.
    # 그래프에서는 빈 구간으로 남기고 회색 영역으로 별도 표시한다.
    annual.loc[annual.index.isin(MISSING_YEARS), ["평균기온", "최고기온", "최저기온"]] = float("nan")

    # 데이터에 존재하는 첫해~마지막해 사이의 모든 연도를 생성해 결측 연도를 명시적으로 유지
    if not annual.empty:
        full_years = range(int(annual.index.min()), int(annual.index.max()) + 1)
        annual = annual.reindex(full_years)
        annual.index.name = "연도"
        annual["관측일수"] = annual["관측일수"].fillna(0)

    # 5개 연도의 연평균기온 이동평균. 결측 구간을 가로질러 선을 연결하지 않도록
    # 5개 값이 모두 존재할 때만 계산한다.
    annual["5년 이동평균"] = annual["평균기온"].rolling(window=5, min_periods=5).mean()
    return df, annual


st.title("서울 연도별 기온 변화")
st.caption("일별 기온 자료를 연도별로 요약하고, 5년 이동평균과 함께 확인합니다.")

uploaded = st.sidebar.file_uploader(
    "CSV 파일 선택 (선택 사항)", type=["csv"],
    help="기본 파일명은 seoul_temperature.csv입니다. 다른 위치에 있다면 업로드하세요."
)

try:
    if uploaded is not None:
        raw, annual = load_data(uploaded.getvalue())
    else:
        raw, annual = load_data()
except FileNotFoundError:
    st.error(
        "seoul_temperature.csv 파일을 찾을 수 없습니다. "
        "app.py와 같은 폴더에 CSV를 두거나 왼쪽 사이드바에서 업로드하세요."
    )
    st.stop()
except Exception as exc:
    st.error(f"CSV를 읽는 중 문제가 발생했습니다: {exc}")
    st.stop()

if annual.empty:
    st.warning("표시할 기온 데이터가 없습니다.")
    st.stop()

min_year, max_year = int(annual.index.min()), int(annual.index.max())
st.sidebar.header("조회 범위")
year_range = st.sidebar.slider(
    "연도 범위",
    min_value=min_year,
    max_value=max_year,
    value=(max(min_year, 1907), max_year),
    step=1,
)

start_year, end_year = year_range
selected = annual.loc[start_year:end_year].copy()
selected_raw = raw[raw["연도"].between(start_year, end_year)].copy()\n# 불완전한 1950~1953년은 선택 구간 요약 통계에서도 제외\nselected_raw = selected_raw[~selected_raw["연도"].isin(MISSING_YEARS)]

# 통계는 관측된 날짜만 사용한다. 결측 연도(1950~1953)는 연도 통계에서 제외된다.
mean_temp = selected_raw[AVG_COL].mean()
max_temp = selected_raw[MAX_COL].max()
min_temp = selected_raw[MIN_COL].min()

c1, c2, c3 = st.columns(3)
c1.metric("선택 구간 평균기온", "—" if pd.isna(mean_temp) else f"{mean_temp:.1f} °C")
c2.metric("선택 구간 최고기온", "—" if pd.isna(max_temp) else f"{max_temp:.1f} °C")
c3.metric("선택 구간 최저기온", "—" if pd.isna(min_temp) else f"{min_temp:.1f} °C")

fig = go.Figure()
fig.add_trace(
    go.Scatter(
        x=selected.index,
        y=selected["평균기온"],
        mode="lines+markers",
        name="연평균기온",
        connectgaps=False,
        line=dict(width=2),
        marker=dict(size=4),
        hovertemplate="연도: %{x}년<br>평균기온: %{y:.2f} °C<extra></extra>",
    )
)
fig.add_trace(
    go.Scatter(
        x=selected.index,
        y=selected["5년 이동평균"],
        mode="lines",
        name="5년 이동평균",
        connectgaps=False,
        line=dict(width=3, dash="dash"),
        hovertemplate="연도: %{x}년<br>5년 이동평균: %{y:.2f} °C<extra></extra>",
    )
)

# 회색 배경으로 측정 자료의 공백 구간을 표시한다.
gap_start = max(start_year, 1950)
gap_end = min(end_year, 1953)
if gap_start <= gap_end:
    fig.add_vrect(
        x0=gap_start - 0.5,
        x1=gap_end + 0.5,
        fillcolor="gray",
        opacity=0.22,
        line_width=0,
        layer="below",
        annotation_text="측정되지 않음",
        annotation_position="top",
        annotation_font=dict(color="gray", size=13),
    )

fig.update_layout(
    template="plotly_white",
    height=560,
    xaxis_title="연도",
    yaxis_title="기온 (°C)",
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    margin=dict(l=20, r=20, t=70, b=20),
)
fig.update_xaxes(dtick=max(1, (end_year - start_year) // 15 or 1), tickformat="d")
fig.update_yaxes(zeroline=True, zerolinecolor="lightgray")
st.plotly_chart(fig, use_container_width=True)

st.subheader("연도별 통계")
display_df = selected[["평균기온", "최고기온", "최저기온", "관측일수"]].copy()
display_df.index.name = "연도"
display_df["평균기온"] = display_df["평균기온"].round(2)
display_df["최고기온"] = display_df["최고기온"].round(2)
display_df["최저기온"] = display_df["최저기온"].round(2)
display_df["관측일수"] = display_df["관측일수"].astype(int)
st.dataframe(display_df, use_container_width=True)

if any(start_year <= y <= end_year for y in MISSING_YEARS):
    st.info(
        "회색 구간(1950~1953년)은 관측 자료가 없거나 불완전한 기간으로 처리했습니다. "
        "해당 연도의 기온 선과 5년 이동평균은 표시하지 않습니다."
    )

st.caption("참고: 선택 구간 통계는 원본 일별 관측값을 기준으로 계산하며, 결측 날짜는 계산에서 제외됩니다.")
