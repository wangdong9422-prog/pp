# app.py
import io, glob
import pandas as pd
import streamlit as st
import plotly.express as px

# ---------------- Page config ----------------
st.set_page_config(
    page_title="국민연금 해외주식 투자정보 대시보드",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📊 국민연금 해외주식 투자정보 대시보드")

# ---------------- Data Loader ----------------
@st.cache_data
def load_np_data():
    # 저장소 내 CSV 자동 탐색 (파일명 힌트 포함/미포함 모두 시도)
    cand = sorted([p for p in glob.glob("*.csv") if "국민연금" in p])
    if not cand:
        cand = sorted(glob.glob("*.csv"))
    if not cand:
        return None, None

    for fname in cand:
        raw = open(fname, "rb").read()
        for enc in ["utf-8", "utf-8-sig", "cp949", "euc-kr"]:
            try:
                df = pd.read_csv(io.BytesIO(raw), encoding=enc)
                return df, fname
            except Exception:
                pass
    return None, None

df, used_file = load_np_data()
if df is None:
    st.error("CSV 파일을 찾지 못했어요. 저장소에 CSV를 올렸는지 확인해주세요.")
    st.stop()

st.caption(f"사용 중인 파일: **{used_file}**")

# 컬럼 표준화(예상 스키마)
# 번호, 종목명, 평가액(억 원), 자산군 내 비중(퍼센트), 지분율(퍼센트)
# 쉼표/문자 섞인 숫자 처리
for c in df.columns:
    if df[c].dtype == "object":
        try:
            df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", ""), errors="ignore")
        except Exception:
            pass

# 컬럼 존재 여부 체크
name_col = "종목명" if "종목명" in df.columns else df.columns[1]
val_col  = "평가액(억 원)" if "평가액(억 원)" in df.columns else df.select_dtypes("number").columns[0]
wgt_col  = "자산군 내 비중(퍼센트)" if "자산군 내 비중(퍼센트)" in df.columns else None
own_col  = "지분율(퍼센트)" if "지분율(퍼센트)" in df.columns else None

# ---------------- Sidebar ----------------
with st.sidebar:
    st.header("🎛 필터 & 옵션")

    # 검색어
    keyword = st.text_input("🔎 종목명 검색", "")

    # Top N
    top_n = st.slider("Top N (랭킹/차트)", 5, 50, 20)

    # 숫자 범위 필터
    st.markdown("**📏 범위 필터**")
    # 평가액
    vmin, vmax = float(pd.to_numeric(df[val_col], errors="coerce").min()), float(pd.to_numeric(df[val_col], errors="coerce").max())
    val_range = st.slider(f"{val_col} 범위", min_value=vmin, max_value=vmax, value=(vmin, vmax))
    # 지분율/비중(있을 때만)
    own_range = None
    if own_col and pd.api.types.is_numeric_dtype(df[own_col]):
        omin, omax = float(df[own_col].min()), float(df[own_col].max())
        own_range = st.slider(f"{own_col} 범위", min_value=omin, max_value=omax, value=(omin, omax))
    wgt_range = None
    if wgt_col and pd.api.types.is_numeric_dtype(df[wgt_col]):
        wmin, wmax = float(df[wgt_col].min()), float(df[wgt_col].max())
        wgt_range = st.slider(f"{wgt_col} 범위", min_value=wmin, max_value=wmax, value=(wmin, wmax))

    # 차트 테마
    theme = st.selectbox("🎨 차트 테마", ["default", "pastel", "vivid", "mono"], index=0)

# 필터 적용
df_f = df.copy()
if keyword.strip():
    df_f = df_f[df_f[name_col].astype(str).str.contains(keyword.strip(), case=False, na=False)]

df_f = df_f[pd.to_numeric(df_f[val_col], errors="coerce").between(val_range[0], val_range[1], inclusive="both")]
if own_range and own_col in df_f.columns:
    df_f = df_f[pd.to_numeric(df_f[own_col], errors="coerce").between(own_range[0], own_range[1], inclusive="both")]
if wgt_range and wgt_col in df_f.columns:
    df_f = df_f[pd.to_numeric(df_f[wgt_col], errors="coerce").between(wgt_range[0], wgt_range[1], inclusive="both")]

st.success(f"현재 필터 결과: **{len(df_f):,} / {len(df):,}** rows")

def palette(t):
    if t == "pastel": return px.colors.qualitative.Set2
    if t == "vivid":  return px.colors.qualitative.Bold
    if t == "mono":   return px.colors.qualitative.Prism
    return px.colors.qualitative.Safe
colors = palette(theme)

# ---------------- Layout: 3 Columns ----------------
col = st.columns((1.5, 4.5, 2), gap="medium")

# ===== col[0]: 요약 지표 =====
with col[0]:
    st.subheader("📊 개요")

    rows = len(df_f)
    cols = df_f.shape[1]
    total_valuation = pd.to_numeric(df_f[val_col], errors="coerce").sum()
    topN_share = 0.0
    if wgt_col and wgt_col in df_f.columns:
        topN_share = df_f.sort_values(val_col, ascending=False).head(top_n)[wgt_col].sum()

    m1, m2, m3 = st.columns(3)
    m1.metric("Rows", f"{rows:,}")
    m2.metric("총 평가액(억 원)", f"{total_valuation:,.0f}")
    m3.metric(f"Top {top_n} 비중(합계)", f"{topN_share:.2f}%" if topN_share else "-")

    st.divider()
    st.markdown(f"**상위 {top_n} 종목({val_col} 기준)**")
    top_tbl = df_f.sort_values(val_col, ascending=False).head(top_n)[[name_col, val_col] + ([wgt_col] if wgt_col else []) + ([own_col] if own_col else [])]
    st.dataframe(top_tbl, use_container_width=True, hide_index=True)

# ===== col[1]: 주요 시각화 =====
with col[1]:
    st.subheader("📈 시각화")

    # 1) Top N 막대 (평가액)
    top_df = df_f.sort_values(val_col, ascending=False).head(top_n)
    fig_top = px.bar(
        top_df,
        x=name_col, y=val_col,
        color=name_col,
        title=f"Top {top_n} {name_col} (by {val_col})",
        text=val_col,
        color_discrete_sequence=colors,
    )
    fig_top.update_traces(texttemplate="%{text:.2s}", textposition="outside")
    fig_top.update_layout(xaxis_title="", yaxis_title=val_col)
    st.plotly_chart(fig_top, use_container_width=True)

    st.divider()

    # 2) 지분율/비중 분포(있을 때만)
    if own_col and pd.api.types.is_numeric_dtype(df_f[own_col]):
        st.markdown(f"**{own_col} 분포**")
        st.plotly_chart(
            px.histogram(df_f, x=own_col, nbins=30, color_discrete_sequence=colors),
            use_container_width=True
        )

    if wgt_col and pd.api.types.is_numeric_dtype(df_f[wgt_col]):
        st.markdown(f"**{wgt_col} 분포**")
        st.plotly_chart(
            px.histogram(df_f, x=wgt_col, nbins=30, color_discrete_sequence=colors),
            use_container_width=True
        )

# ===== col[2]: 랭킹/다운로드 =====
with col[2]:
    st.subheader("🏆 랭킹 & 다운로드")

    metric = st.selectbox("정렬 지표", [val_col] + ([wgt_col] if wgt_col else []) + ([own_col] if own_col else []))
    asc = st.toggle("오름차순 정렬", value=False)
    rank = df_f.sort_values(metric, ascending=asc).head(top_n)[[name_col, val_col] + ([wgt_col] if wgt_col else []) + ([own_col] if own_col else [])]
    st.dataframe(rank, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("**데이터 미리보기 (상위 200행)**")
    st.dataframe(df_f.head(200), use_container_width=True, hide_index=True)

    csv = df_f.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ 필터링 결과 CSV 다운로드", data=csv, file_name="filtered_result.csv", mime="text/csv")

    with st.expander("ℹ️ 안내"):
        st.markdown(
            "- 파일 인코딩은 `utf-8 → cp949 → euc-kr` 순으로 자동 시도합니다.\n"
            f"- 사용 컬럼: `{name_col}`, `{val_col}`"
            + (f", `{wgt_col}`" if wgt_col else "")
            + (f", `{own_col}`" if own_col else "")
            + "\n- 사이드바에서 검색·범위·Top N·테마를 조절하세요."
        )
