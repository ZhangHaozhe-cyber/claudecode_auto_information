"""
中国医药产业政策分析看板

部署：streamlit run app.py
数据：output/cleaned_policies.parquet（由 scripts/clean_data.py 生成）
本地更新：python pipeline/run_full_pipeline.py
推送 HF：git add output/cleaned_policies.parquet && git commit && git push
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
from st_aggrid.shared import JsCode

# ── 页面配置 ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="中国医药产业政策分析仪表板",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded",
)

PARQUET_PATH = Path(__file__).parent / "output" / "cleaned_policies.parquet"

# ── 配色与常量 ────────────────────────────────────────────────────────────────

DEPT_COLORS = {
    "国务院": "#2166AC",
    "国家医疗保障局": "#1A9641",
    "国家药品监督管理局": "#E7731C",
    "国家卫生健康委员会": "#9B2335",
    "工业和信息化部": "#6A4C93",
    "国家发展和改革委员会": "#1D6996",
}
PLOTLY_TEMPLATE = "plotly_white"
FONT_FAMILY = "Arial, 'Microsoft YaHei', sans-serif"

TAG_COLS = ["tag_集采", "tag_医保", "tag_创新药", "tag_医改", "tag_临床试验", "tag_药监", "tag_疫苗"]

NHSA_COL_MAP = {
    "col14": "医保动态",
    "col147": "集采专栏",
    "col104": "政策法规",
    "col105": "政策解读",
}

# ── 数据加载 ────────────────────────────────────────────────────────────────

@st.cache_data
def load_data() -> pd.DataFrame:
    if not PARQUET_PATH.exists():
        st.error(
            f"**数据文件不存在**：`{PARQUET_PATH}`\n\n"
            "请先在本地运行：\n```\npython -X utf8 scripts/clean_data.py\n```"
        )
        st.stop()
    df = pd.read_parquet(PARQUET_PATH)
    df["pub_date"] = pd.to_datetime(df["pub_date"])
    for col in TAG_COLS:
        if col in df.columns:
            df[col] = df[col].astype(bool)
    # 美化 source_col 显示
    if "source_col" in df.columns:
        df["source_col_label"] = df["source_col"].map(NHSA_COL_MAP).fillna(df["source_col"])
    return df


df_full = load_data()

# ── 侧边栏 ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("筛选条件")
    st.caption("所有条件同时生效（AND），政策主题内为 OR 逻辑")

    year_min = int(df_full["year"].min())
    year_max = int(df_full["year"].max())
    year_range = st.slider("发文年份范围", min_value=year_min, max_value=year_max,
                           value=(year_min, year_max))

    all_depts = sorted(df_full["department"].unique().tolist())
    selected_depts = st.multiselect("发文部门", options=all_depts, default=all_depts)

    st.markdown("**按政策主题筛选**（勾选后只显示含该主题的政策）")
    selected_tags = []
    for col in TAG_COLS:
        label = col.replace("tag_", "")
        count = int(df_full[col].sum())
        if st.checkbox(f"{label}（{count} 条）", value=False, key=col):
            selected_tags.append(col)

    keyword = st.text_input("标题关键词搜索", placeholder="输入关键词…")

    st.divider()
    if st.button("清空所有筛选"):
        st.rerun()

# ── 过滤逻辑 ────────────────────────────────────────────────────────────────

df = df_full.copy()
df = df[(df["year"] >= year_range[0]) & (df["year"] <= year_range[1])]
if selected_depts:
    df = df[df["department"].isin(selected_depts)]
if selected_tags:
    mask = pd.Series(False, index=df.index)
    for col in selected_tags:
        mask = mask | df[col]
    df = df[mask]
if keyword.strip():
    df = df[df["title"].str.contains(keyword.strip(), na=False)]
df = df.sort_values("pub_date", ascending=False).reset_index(drop=True)

# ── AgGrid 链接渲染 ──────────────────────────────────────────────────────────

LINK_RENDERER = JsCode("""
function(params) {
    if (!params.value) return '';
    return '<a href="' + params.value + '" target="_blank" rel="noopener" '
         + 'style="color:#2166AC;text-decoration:none;">🔗 原文</a>';
}
""")


def make_aggrid(display_df: pd.DataFrame, col_config: dict, height: int = 520) -> None:
    """通用 AgGrid 渲染函数。col_config: {列名: width}"""
    gb = GridOptionsBuilder.from_dataframe(display_df)
    gb.configure_default_column(filterable=True, sortable=True, resizable=True)
    for col, width in col_config.items():
        if col == "标题":
            gb.configure_column(col, minWidth=width, wrapText=True, autoHeight=True)
        elif col == "链接":
            gb.configure_column(col, cellRenderer=LINK_RENDERER, width=width,
                                filterable=False, sortable=False)
        elif col == "发布日期":
            gb.configure_column(col, width=width, sort="desc", pinned="left")
        else:
            gb.configure_column(col, width=width)
    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=20)
    gb.configure_grid_options(rowHeight=56, suppressMovableColumns=True)
    AgGrid(
        display_df,
        gridOptions=gb.build(),
        update_mode=GridUpdateMode.NO_UPDATE,
        height=height,
        fit_columns_on_grid_load=False,
        allow_unsafe_jscode=True,
        enable_enterprise_modules=False,
        theme="alpine",
    )


def export_button(df_display: pd.DataFrame, label: str = "📥 导出当前视图为 CSV", key: str = "export") -> None:
    csv_bytes = df_display.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    fname = f"policies_{year_range[0]}-{year_range[1]}.csv"
    st.download_button(label, data=csv_bytes, file_name=fname, mime="text/csv",
                       key=key,
                       help="UTF-8 BOM 编码，可直接在 Excel 中打开并正确显示中文")


def placeholder_tab(dept_name: str, sources: list, eta: str = "2026年Q3") -> None:
    st.info(f"**{dept_name}** 数据模块建设中，尚未接入自动化爬虫")
    st.markdown("**计划数据来源：**")
    for s in sources:
        st.markdown(f"- {s}")
    st.caption(f"预计上线：{eta}")
    st.divider()
    st.markdown(
        "如需提前使用，可在本地手动抓取后运行 `pipeline/run_full_pipeline.py --skip-scrape`，"
        "然后将 parquet 推送至 HF Space。"
    )


# ── 页面标题 ────────────────────────────────────────────────────────────────

st.title("💊 中国医药产业政策分析仪表板")
st.caption(
    f"数据来源：国务院（2010–2026）& 国家医保局  |  "
    f"筛选结果：**{len(df)}** 条 / 共 {len(df_full)} 条"
)

# ── Tab 布局 ────────────────────────────────────────────────────────────────

(tab_overview, tab_gwy, tab_nhsa,
 tab_nmpa, tab_nhc, tab_miit, tab_ndrc, tab_local) = st.tabs([
    "📊 总览",
    "🏛 国务院",
    "🏥 国家医保局",
    "💊 国家药监局",
    "🩺 国家卫健委",
    "🏭 工信部",
    "📈 发改委",
    "🗺 地方政府",
])

# ════════════════════════════════════════════════════════
# Tab 1：总览
# ════════════════════════════════════════════════════════
with tab_overview:
    st.subheader("年度政策发文数量趋势")

    col_l, col_r = st.columns(2)

    with col_l:
        yearly_dept = df.groupby(["year", "department"]).size().reset_index(name="count")
        fig_trend = px.line(
            yearly_dept, x="year", y="count", color="department", markers=True,
            color_discrete_map=DEPT_COLORS,
            labels={"year": "年份", "count": "政策数量", "department": "发文部门"},
            template=PLOTLY_TEMPLATE,
        )
        fig_trend.update_layout(
            font_family=FONT_FAMILY,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
            margin=dict(t=30, b=50), xaxis=dict(dtick=2, tickangle=-45),
            hovermode="x unified",
        )
        st.plotly_chart(fig_trend, use_container_width=True)

    with col_r:
        dept_counts = df["department"].value_counts().reset_index()
        dept_counts.columns = ["department", "count"]
        fig_dept = px.bar(
            dept_counts, x="department", y="count", color="department",
            color_discrete_map=DEPT_COLORS,
            labels={"department": "发文部门", "count": "政策数量"},
            template=PLOTLY_TEMPLATE, text_auto=True,
        )
        fig_dept.update_layout(
            showlegend=False, font_family=FONT_FAMILY,
            margin=dict(t=30, b=60), xaxis=dict(title=""),
        )
        st.plotly_chart(fig_dept, use_container_width=True)

    # 政策主题实施时间线热力图
    st.subheader("政策主题实施时间线")
    st.caption("颜色越深表示该年度含该主题的政策越多，可用于定位政策冲击节点")
    all_years = sorted(df["year"].unique().tolist())
    heat_z, heat_y = [], []
    for col in TAG_COLS:
        label = col.replace("tag_", "")
        counts = (df[df[col] == True].groupby("year").size()
                  .reindex(all_years, fill_value=0).tolist())
        heat_z.append(counts)
        heat_y.append(label)

    if all_years and any(sum(row) > 0 for row in heat_z):
        fig_heat = go.Figure(data=go.Heatmap(
            z=heat_z, x=[str(y) for y in all_years], y=heat_y,
            colorscale="Blues", text=heat_z, texttemplate="%{text}",
            textfont={"size": 12}, showscale=True,
            colorbar=dict(title="条数", thickness=12),
        ))
        fig_heat.update_layout(
            template=PLOTLY_TEMPLATE, font_family=FONT_FAMILY,
            xaxis=dict(title="年份", tickangle=-45),
            yaxis=dict(title="政策主题", autorange="reversed"),
            margin=dict(t=20, b=60, l=80, r=60), height=300,
        )
        st.plotly_chart(fig_heat, use_container_width=True)

    st.divider()

    # 全量数据表
    st.subheader("政策列表（全部来源）")
    disp_all = df[["pub_date", "title", "department", "policy_type",
                   "tags_display", "link"]].copy()
    disp_all["pub_date"] = disp_all["pub_date"].dt.strftime("%Y-%m-%d")
    disp_all = disp_all.rename(columns={
        "pub_date": "发布日期", "title": "标题", "department": "发文部门",
        "policy_type": "政策类型", "tags_display": "政策主题", "link": "链接",
    })
    make_aggrid(disp_all, {"发布日期": 110, "标题": 380, "发文部门": 145,
                            "政策类型": 120, "政策主题": 180, "链接": 80})

    col_exp, col_stat = st.columns([1, 3])
    with col_exp:
        export_button(disp_all, key="export_all")
    with col_stat:
        tag_summary = {c.replace("tag_", ""): int(df[c].sum()) for c in TAG_COLS}
        hit = {k: v for k, v in tag_summary.items() if v > 0}
        if hit:
            st.caption("政策主题：" + "  |  ".join(f"**{k}** {v}条" for k, v in hit.items()))


# ════════════════════════════════════════════════════════
# Tab 2：国务院
# ════════════════════════════════════════════════════════
with tab_gwy:
    df_gwy = df[df["department"] == "国务院"].copy()

    col1, col2, col3 = st.columns(3)
    col1.metric("政策总数（当前筛选）", len(df_gwy))
    col2.metric("含集采/带量采购", int(df_gwy["tag_集采"].sum()) if "tag_集采" in df_gwy else 0)
    col3.metric("含医保相关", int(df_gwy["tag_医保"].sum()) if "tag_医保" in df_gwy else 0)

    if not df_gwy.empty:
        # 年度趋势
        st.subheader("国务院年度政策数量")
        yearly_gwy = df_gwy.groupby("year").size().reset_index(name="count")
        fig_gwy = px.bar(yearly_gwy, x="year", y="count", template=PLOTLY_TEMPLATE,
                         color_discrete_sequence=["#2166AC"],
                         labels={"year": "年份", "count": "政策数量"}, text_auto=True)
        fig_gwy.update_layout(font_family=FONT_FAMILY, margin=dict(t=20, b=50),
                               xaxis=dict(dtick=2, tickangle=-45))
        st.plotly_chart(fig_gwy, use_container_width=True)

        st.subheader("政策文件列表")
        st.caption("包含文号（如「国办发〔2010〕4号」）和成文日期")

        # 构建显示 DataFrame（含文号、成文日期）
        show_cols = ["pub_date", "cwrq", "fwzh", "title", "policy_type", "tags_display", "link"]
        avail = [c for c in show_cols if c in df_gwy.columns]
        disp_gwy = df_gwy[avail].copy()
        disp_gwy["pub_date"] = disp_gwy["pub_date"].dt.strftime("%Y-%m-%d")
        rename_map = {
            "pub_date": "发布日期", "cwrq": "成文日期", "fwzh": "文号",
            "title": "标题", "policy_type": "政策类型",
            "tags_display": "政策主题", "link": "链接",
        }
        disp_gwy = disp_gwy.rename(columns={k: v for k, v in rename_map.items() if k in disp_gwy.columns})

        col_cfg = {"发布日期": 110, "成文日期": 110, "文号": 160, "标题": 340,
                   "政策类型": 110, "政策主题": 150, "链接": 80}
        make_aggrid(disp_gwy, {k: v for k, v in col_cfg.items() if k in disp_gwy.columns})
        export_button(disp_gwy, key="export_gwy")
    else:
        st.info("当前筛选条件下国务院政策为空，请调整侧边栏筛选条件。")


# ════════════════════════════════════════════════════════
# Tab 3：国家医保局
# ════════════════════════════════════════════════════════
with tab_nhsa:
    df_nhsa = df[df["department"] == "国家医疗保障局"].copy()

    col1, col2, col3 = st.columns(3)
    col1.metric("政策总数（当前筛选）", len(df_nhsa))
    col2.metric("含集采相关", int(df_nhsa["tag_集采"].sum()) if "tag_集采" in df_nhsa else 0)
    col3.metric("含医保相关", int(df_nhsa["tag_医保"].sum()) if "tag_医保" in df_nhsa else 0)

    if not df_nhsa.empty:
        # 来源栏目饼图
        if "source_col_label" in df_nhsa.columns:
            st.subheader("政策来源栏目分布")
            col_pie, col_space = st.columns([1, 1])
            with col_pie:
                col_counts = df_nhsa["source_col_label"].value_counts().reset_index()
                col_counts.columns = ["栏目", "数量"]
                fig_pie = px.pie(col_counts, names="栏目", values="数量",
                                 color_discrete_sequence=px.colors.sequential.Blues_r,
                                 template=PLOTLY_TEMPLATE)
                fig_pie.update_layout(font_family=FONT_FAMILY, margin=dict(t=10, b=10))
                st.plotly_chart(fig_pie, use_container_width=True)

        st.subheader("政策文件列表")
        st.caption("来源栏目：col104=政策法规 | col147=集采专栏 | col105=政策解读 | col14=医保动态")

        show_cols = ["pub_date", "title", "policy_type", "source_col_label", "tags_display", "link"]
        avail = [c for c in show_cols if c in df_nhsa.columns]
        disp_nhsa = df_nhsa[avail].copy()
        disp_nhsa["pub_date"] = disp_nhsa["pub_date"].dt.strftime("%Y-%m-%d")
        disp_nhsa = disp_nhsa.rename(columns={
            "pub_date": "发布日期", "title": "标题", "policy_type": "政策类型",
            "source_col_label": "来源栏目", "tags_display": "政策主题", "link": "链接",
        })
        col_cfg = {"发布日期": 110, "标题": 360, "政策类型": 120,
                   "来源栏目": 110, "政策主题": 150, "链接": 80}
        make_aggrid(disp_nhsa, {k: v for k, v in col_cfg.items() if k in disp_nhsa.columns})
        export_button(disp_nhsa, key="export_nhsa")
    else:
        st.info("当前筛选条件下国家医保局政策为空，请调整侧边栏筛选条件。")


# ════════════════════════════════════════════════════════
# Tab 4-8：占位页
# ════════════════════════════════════════════════════════
with tab_nmpa:
    placeholder_tab("国家药品监督管理局（NMPA）", [
        "nmpa.gov.cn 药品资讯（需浏览器自动化绕过412防爬）",
        "nmpa.gov.cn 公告通告",
        "nmpa.gov.cn 审评公示、注册批件",
    ])

with tab_nhc:
    placeholder_tab("国家卫生健康委员会（NHC）", [
        "nhc.gov.cn 新闻发布（需浏览器自动化）",
        "nhc.gov.cn 政策解读",
        "nhc.gov.cn 诊疗指南、规范",
    ])

with tab_miit:
    placeholder_tab("工业和信息化部（MIIT）", [
        "miit.gov.cn 政策文件（AJAX动态加载，需 Playwright）",
        "生物医药产业专项政策、数字化转型文件",
    ])

with tab_ndrc:
    placeholder_tab("国家发展和改革委员会（NDRC）", [
        "ndrc.gov.cn 产业政策：医药制造业相关",
        "ndrc.gov.cn 价格监管：药价改革文件",
        "ndrc.gov.cn 医疗基础设施投资计划",
    ], eta="2026年Q4")

with tab_local:
    placeholder_tab("地方政府", [
        "各省医保局政策（上海、广东、北京、浙江等）",
        "省级集采联盟公告（如京津冀、广东联盟等）",
        "地方配套实施细则（跟随国家集采政策）",
    ], eta="2026年Q4")

# ── 页脚 ───────────────────────────────────────────────────────────────────

st.divider()
st.caption(
    "数据更新：`python -X utf8 pipeline/run_full_pipeline.py` → "
    "`git add output/cleaned_policies.parquet && git commit && git push`"
)
