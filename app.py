
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="서울 기온 변화 대시보드",
    page_icon="🌡️",
    layout="wide"
)

CSV_PATH = "seoul_temperature.csv"
DATE_COL = "날짜"
AVG_COL = "평균기온(℃)"
MIN_COL = "최저기온(℃)"
MAX_COL = "최고기온(℃)"
MISSING_YEARS = [1950, 1951, 1952, 1953]


@st.cache_data
def load_data(file_bytes=None):
    if file_bytes is None:
        df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")
    else:
        from io import BytesIO
        df = pd.read_csv(BytesIO(file_bytes), encoding="utf-8-sig")

    required = [DATE_COL, AVG_COL, MIN_COL, MAX_COL]
    missing_cols = [c for c in required if c not in df.columns]
    if missing_cols:
        raise ValueError(f"CSV에 필요한 컬럼이 없습니다: {', '.join(missing_cols)}")

    # 날짜 앞의 탭 문자와 앞뒤 공백 제거
    df[DATE_COL] = pd.to_datetime(
        df[DATE_COL].astype(str).str.strip(),
        errors="coerce"
    )

    for col in [AVG_COL, MIN_COL, MAX_COL]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=[DATE_COL]).copy()
    df["연도"] = df[DATE_COL].dt.year.astype(int)
    df["월"] = df[DATE_COL].dt.month.astype(int)

    # 일교차 컬럼 생성
    df["일교차(℃)"] = df[MAX_COL] - df[MIN_COL]

    annual = df.groupby("연도").agg(
        평균기온=(AVG_COL, "mean"),
        최고기온=(MAX_COL, "max"),
        최저기온=(MIN_COL, "min"),
        평균일교차=("일교차(℃)", "mean"),
        관측일수=(AVG_COL, "count")
    )

    # 불완전한 연도는 분석값에서 제외
    annual.loc[
        annual.index.isin(MISSING_YEARS),
        ["평균기온", "최고기온", "최저기온", "평균일교차"]
    ] = float("nan")

    if not annual.empty:
        years = range(
            int(annual.index.min()),
            int(annual.index.max()) + 1
        )
        annual = annual.reindex(years)
        annual.index.name = "연도"
        annual["관측일수"] = annual["관측일수"].fillna(0)

    # 5년 이동평균
    annual["5년 이동평균"] = (
        annual["평균기온"]
        .rolling(window=5, min_periods=5)
        .mean()
    )

    return df, annual


st.title("서울 연도별 기온 변화")
st.caption("서울의 기온 변화와 월별 분포를 분석하는 대시보드")

uploaded = st.sidebar.file_uploader(
    "CSV 파일 업로드",
    type=["csv"]
)

try:
    if uploaded is not None:
        raw, annual = load_data(uploaded.getvalue())
    else:
        raw, annual = load_data()
except FileNotFoundError:
    st.error(
        "seoul_temperature.csv 파일을 찾을 수 없습니다. "
        "app.py와 같은 폴더에 CSV를 두거나 사이드바에서 업로드하세요."
    )
    st.stop()
except Exception as exc:
    st.error(f"CSV를 읽는 중 오류가 발생했습니다: {exc}")
    st.stop()

if annual.empty:
    st.warning("표시할 데이터가 없습니다.")
    st.stop()


# 사이드바 연도 범위 선택
min_year = int(annual.index.min())
max_year = int(annual.index.max())

st.sidebar.header("조회 범위")

default_start = min(max(min_year, 1907), max_year)

start_year, end_year = st.sidebar.slider(
    "연도 범위",
    min_value=min_year,
    max_value=max_year,
    value=(default_start, max_year),
    step=1
)

selected = annual.loc[start_year:end_year].copy()

# 결측 연도는 통계 및 순위에서 제외
selected_raw = raw[
    raw["연도"].between(start_year, end_year)
].copy()

selected_raw = selected_raw[
    ~selected_raw["연도"].isin(MISSING_YEARS)
].copy()


# 요약 통계
mean_temp = selected_raw[AVG_COL].mean()
max_temp = selected_raw[MAX_COL].max()
min_temp = selected_raw[MIN_COL].min()

c1, c2, c3 = st.columns(3)

c1.metric(
    "선택 구간 평균기온",
    "—" if pd.isna(mean_temp) else f"{mean_temp:.1f} °C"
)
c2.metric(
    "선택 구간 최고기온",
    "—" if pd.isna(max_temp) else f"{max_temp:.1f} °C"
)
c3.metric(
    "선택 구간 최저기온",
    "—" if pd.isna(min_temp) else f"{min_temp:.1f} °C"
)


# 1. 연도별 평균기온 및 5년 이동평균
st.subheader("1. 연도별 평균기온 및 5년 이동평균")

fig = go.Figure()

fig.add_trace(go.Scatter(
    x=selected.index,
    y=selected["평균기온"],
    mode="lines+markers",
    name="연평균기온",
    connectgaps=False,
    hovertemplate="%{x}년<br>평균기온: %{y:.2f} °C<extra></extra>"
))

fig.add_trace(go.Scatter(
    x=selected.index,
    y=selected["5년 이동평균"],
    mode="lines",
    name="5년 이동평균",
    line=dict(dash="dash", width=3),
    connectgaps=False,
    hovertemplate="%{x}년<br>5년 이동평균: %{y:.2f} °C<extra></extra>"
))

gap_start = max(start_year, 1950)
gap_end = min(end_year, 1953)

if gap_start <= gap_end:
    fig.add_vrect(
        x0=gap_start - 0.5,
        x1=gap_end + 0.5,
        fillcolor="gray",
        opacity=0.25,
        line_width=0,
        layer="below",
        annotation_text="측정되지 않음",
        annotation_position="top",
        annotation_font=dict(color="gray")
    )

fig.update_layout(
    template="plotly_white",
    height=500,
    xaxis_title="연도",
    yaxis_title="기온 (°C)",
    hovermode="x unified",
    legend=dict(orientation="h", y=1.02, x=0),
    margin=dict(l=20, r=20, t=70, b=20)
)

fig.update_xaxes(
    dtick=max(1, (end_year - start_year) // 15 or 1),
    tickformat="d"
)

st.plotly_chart(fig, use_container_width=True)


# 2. 월별 평균기온 히트맵
st.subheader("2. 월별 평균기온 히트맵")

heat_raw = raw[
    raw["연도"].between(start_year, end_year)
    & ~raw["연도"].isin(MISSING_YEARS)
].copy()

monthly = heat_raw.pivot_table(
    index="연도",
    columns="월",
    values=AVG_COL,
    aggfunc="mean"
).reindex(
    index=range(start_year, end_year + 1),
    columns=range(1, 13)
)

# 결측 연도의 히트맵 셀은 비워 둠
monthly.loc[
    monthly.index.isin(MISSING_YEARS), :
] = float("nan")

heat_fig = go.Figure(data=go.Heatmap(
    z=monthly.values,
    x=list(range(1, 13)),
    y=list(monthly.index),
    colorscale="RdYlBu_r",
    colorbar=dict(title="평균기온 (°C)"),
    hovertemplate=(
        "연도: %{y}년<br>"
        "월: %{x}월<br>"
        "평균기온: %{z:.2f} °C<extra></extra>"
    ),
    hoverongaps=False
))

# 결측 기간을 회색으로 덮어 표시
if gap_start <= gap_end:
    heat_fig.add_shape(
        type="rect",
        x0=0.5,
        x1=12.5,
        y0=gap_start - 0.5,
        y1=gap_end + 0.5,
        fillcolor="gray",
        opacity=0.45,
        line_width=0,
        layer="above"
    )

    heat_fig.add_annotation(
        x=6.5,
        y=(gap_start + gap_end) / 2,
        text="측정되지 않음",
        showarrow=False,
        font=dict(color="black", size=12)
    )

heat_fig.update_layout(
    template="plotly_white",
    height=max(450, min(1000, 250 + len(monthly) * 12)),
    xaxis_title="월",
    yaxis_title="연도",
    margin=dict(l=20, r=20, t=30, b=20)
)

heat_fig.update_xaxes(
    tickmode="array",
    tickvals=list(range(1, 13)),
    ticktext=[f"{m}월" for m in range(1, 13)]
)

heat_fig.update_yaxes(
    autorange="reversed",
    dtick=max(1, (end_year - start_year) // 30 or 1)
)

st.plotly_chart(heat_fig, use_container_width=True)


# 3. 최고기온 상위 10일
st.subheader("3. 최고기온 상위 10일")

top10 = (
    selected_raw
    .dropna(subset=[MAX_COL])
    .nlargest(10, MAX_COL)
    [[DATE_COL, MAX_COL, AVG_COL, MIN_COL, "일교차(℃)"]]
    .copy()
)

top10[DATE_COL] = top10[DATE_COL].dt.strftime("%Y-%m-%d")

top10 = top10.rename(columns={
    DATE_COL: "날짜",
    MAX_COL: "최고기온(℃)",
    AVG_COL: "평균기온(℃)",
    MIN_COL: "최저기온(℃)"
})

st.dataframe(
    top10.reset_index(drop=True),
    use_container_width=True,
    hide_index=True
)


# 4. 최저기온 하위 10일
st.subheader("4. 최저기온 하위 10일")

bottom10 = (
    selected_raw
    .dropna(subset=[MIN_COL])
    .nsmallest(10, MIN_COL)
    [[DATE_COL, MIN_COL, AVG_COL, MAX_COL, "일교차(℃)"]]
    .copy()
)

bottom10[DATE_COL] = bottom10[DATE_COL].dt.strftime("%Y-%m-%d")

bottom10 = bottom10.rename(columns={
    DATE_COL: "날짜",
    MIN_COL: "최저기온(℃)",
    AVG_COL: "평균기온(℃)",
    MAX_COL: "최고기온(℃)"
})

st.dataframe(
    bottom10.reset_index(drop=True),
    use_container_width=True,
    hide_index=True
)


# 5. 연도별 평균 일교차
st.subheader("5. 연도별 평균 일교차")

gap_fig = go.Figure()

gap_fig.add_trace(go.Scatter(
    x=selected.index,
    y=selected["평균일교차"],
    mode="lines+markers",
    name="평균 일교차",
    connectgaps=False,
    hovertemplate="%{x}년<br>평균 일교차: %{y:.2f} °C<extra></extra>"
))

if gap_start <= gap_end:
    gap_fig.add_vrect(
        x0=gap_start - 0.5,
        x1=gap_end + 0.5,
        fillcolor="gray",
        opacity=0.25,
        line_width=0,
        layer="below",
        annotation_text="측정되지 않음",
        annotation_position="top",
        annotation_font=dict(color="gray")
    )

gap_fig.update_layout(
    template="plotly_white",
    height=420,
    xaxis_title="연도",
    yaxis_title="평균 일교차 (°C)",
    hovermode="x unified",
    margin=dict(l=20, r=20, t=30, b=20)
)

gap_fig.update_xaxes(
    dtick=max(1, (end_year - start_year) // 15 or 1),
    tickformat="d"
)

st.plotly_chart(gap_fig, use_container_width=True)


# 6. 연도별 통계표
st.subheader("6. 연도별 통계")

display_df = selected[
    ["평균기온", "최고기온", "최저기온", "평균일교차", "관측일수"]
].copy()

display_df.index.name = "연도"

for col in ["평균기온", "최고기온", "최저기온", "평균일교차"]:
    display_df[col] = display_df[col].round(2)

display_df["관측일수"] = display_df["관측일수"].astype(int)

st.dataframe(
    display_df,
    use_container_width=True
)

if any(start_year <= y <= end_year for y in MISSING_YEARS):
    st.info(
        "회색 구간(1950~1953년)은 측정되지 않음으로 표시했습니다. "
        "해당 연도는 기온 통계와 순위 분석에서 제외됩니다."
    )

st.caption(
    "일교차는 최고기온에서 최저기온을 뺀 값입니다. "
    "선택 구간 통계는 결측 연도를 제외한 일별 관측값을 기준으로 계산합니다."
)
