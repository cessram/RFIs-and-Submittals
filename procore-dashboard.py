import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import io

try:
    import openpyxl
except ImportError:
    openpyxl = None

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

# ============================================================
# PAGE CONFIG & LIGHT THEME
# ============================================================
st.set_page_config(page_title="Submittal & RFI Tracker", layout="wide", page_icon="🏗️")

COLORS = {
    "bg": "#FFFFFF",
    "card": "#F8FAFC",
    "accent": "#0D9488",
    "accent2": "#7C3AED",
    "warning": "#D97706",
    "danger": "#DC2626",
    "success": "#059669",
    "text": "#1E293B",
    "muted": "#64748B",
    "blue": "#2563EB",
    "border": "#E2E8F0",
    "grid": "#F1F5F9",
}

st.markdown(f"""
<style>
    .stApp {{
        background-color: {COLORS['bg']};
    }}
    .metric-card {{
        background: {COLORS['card']};
        border: 1px solid {COLORS['border']};
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        transition: transform 0.2s;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }}
    .metric-card:hover {{
        transform: translateY(-2px);
        border-color: {COLORS['accent']};
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    }}
    .metric-value {{
        font-size: 2.2rem;
        font-weight: 700;
        margin: 4px 0;
    }}
    .metric-label {{
        font-size: 0.85rem;
        color: {COLORS['muted']};
        text-transform: uppercase;
        letter-spacing: 1px;
    }}
    .status-open {{ color: {COLORS['warning']}; font-weight: 600; }}
    .status-closed {{ color: {COLORS['success']}; font-weight: 600; }}
    .status-overdue {{ color: {COLORS['danger']}; font-weight: 600; }}
    .section-header {{
        font-size: 1.4rem;
        font-weight: 600;
        color: {COLORS['text']};
        margin: 30px 0 15px 0;
        padding-bottom: 8px;
        border-bottom: 2px solid {COLORS['accent']};
    }}
    .alert-banner {{
        background: #FEF2F2;
        border: 1px solid #FECACA;
        border-left: 4px solid {COLORS['danger']};
        border-radius: 8px;
        padding: 12px 20px;
        margin: 8px 0;
        color: #991B1B;
        font-size: 0.9rem;
    }}
    div[data-testid="stDataFrame"] {{
        border: 1px solid {COLORS['border']};
        border-radius: 8px;
    }}
    .stTabs [data-baseweb="tab-list"] {{
        gap: 8px;
    }}
    .stTabs [data-baseweb="tab"] {{
        background-color: {COLORS['card']};
        border-radius: 8px 8px 0 0;
        padding: 10px 24px;
        color: {COLORS['muted']};
    }}
    .stTabs [aria-selected="true"] {{
        background-color: {COLORS['bg']};
        color: {COLORS['accent']} !important;
        border-bottom: 2px solid {COLORS['accent']};
    }}
</style>
""", unsafe_allow_html=True)


# ============================================================
# SAMPLE DATA GENERATOR
# ============================================================
# ============================================================
# FILE PARSER — CSV, Excel, PDF
# ============================================================
SUPPORTED_TYPES = ["csv", "xlsx", "xls", "pdf"]

def parse_uploaded_file(uploaded_file):
    """Parse CSV, Excel (.xlsx/.xls), or PDF into a DataFrame."""
    if uploaded_file is None:
        return None
    name = uploaded_file.name.lower()

    try:
        if name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        elif name.endswith((".xlsx", ".xls")):
            # Let user pick sheet if multiple exist
            xls = pd.ExcelFile(uploaded_file)
            if len(xls.sheet_names) > 1:
                sheet = st.selectbox(
                    f"Select sheet from **{uploaded_file.name}**",
                    xls.sheet_names, key=f"sheet_{uploaded_file.name}"
                )
            else:
                sheet = xls.sheet_names[0]
            df = pd.read_excel(xls, sheet_name=sheet)
        elif name.endswith(".pdf"):
            if pdfplumber is None:
                st.error("📦 `pdfplumber` is required for PDF import. Install it with: `pip install pdfplumber`")
                return None
            all_rows = []
            with pdfplumber.open(io.BytesIO(uploaded_file.read())) as pdf:
                for page in pdf.pages:
                    table = page.extract_table()
                    if table:
                        all_rows.extend(table)
            if not all_rows:
                st.warning("⚠️ No tables found in the PDF file.")
                return None
            # First row as header
            df = pd.DataFrame(all_rows[1:], columns=all_rows[0])
        else:
            st.error(f"Unsupported file type: {uploaded_file.name}")
            return None

        df.columns = df.columns.str.strip()
        return df

    except Exception as e:
        st.error(f"❌ Error reading **{uploaded_file.name}**: {e}")
        return None


def generate_sample_submittals():
    contractors = ["CRB", "CIMA+", "SMP Engineering", "Icon Electric", "Bird Construction"]
    spec_sections = [
        "03 30 00 - Cast-in-Place Concrete", "07 84 00 - Firestopping",
        "15 01 00 - Mechanical General", "23 05 00 - HVAC Piping",
        "26 05 00 - Electrical General", "28 31 00 - Fire Detection",
        "22 10 00 - Plumbing Piping", "09 90 00 - Painting & Coating",
        "08 11 00 - Steel Doors & Frames", "21 13 00 - Fire Sprinkler Systems",
        "23 73 00 - Air Handling Units", "26 24 00 - Switchboards & Panels",
        "13 34 00 - Cleanroom Construction", "11 48 00 - Pharma Equipment",
    ]
    statuses = ["Open", "Pending Review", "Approved", "Approved as Noted", "Revise & Resubmit", "Rejected"]
    ball_in_court = ["Consultant", "Contractor", "Owner", "Architect"]
    reviewers = ["CRB Design Team", "CIMA+ Review", "Bird PM", "Owner Rep"]

    rows = []
    import random
    random.seed(42)
    for i in range(1, 61):
        created = datetime(2025, 1, 1) + timedelta(days=random.randint(0, 200))
        due = created + timedelta(days=random.randint(7, 21))
        status = random.choice(statuses)
        rows.append({
            "Submittal #": f"SUB-{i:04d}",
            "Title": f"Submittal for {random.choice(spec_sections).split(' - ')[1]}",
            "Spec Section": random.choice(spec_sections),
            "Contractor": random.choice(contractors),
            "Status": status,
            "Ball in Court": random.choice(ball_in_court) if status not in ["Approved", "Rejected"] else "Closed",
            "Reviewer": random.choice(reviewers),
            "Date Created": created.strftime("%Y-%m-%d"),
            "Due Date": due.strftime("%Y-%m-%d"),
            "Date Closed": (due + timedelta(days=random.randint(-3, 10))).strftime("%Y-%m-%d") if status in ["Approved", "Approved as Noted", "Rejected"] else "",
            "Days Open": (datetime.now() - created).days if status not in ["Approved", "Approved as Noted", "Rejected"] else (due - created).days + random.randint(-3, 5),
        })
    return pd.DataFrame(rows)


def generate_sample_rfis():
    contractors = ["CRB", "CIMA+", "SMP Engineering", "Icon Electric", "Bird Construction"]
    disciplines = ["Structural", "Mechanical", "Electrical", "Architectural", "Plumbing", "Fire Protection", "Process/Pharma"]
    statuses = ["Open", "Pending Response", "Closed", "Overdue"]
    priority = ["Low", "Medium", "High", "Critical"]
    cost_impact = ["None", "Potential", "Confirmed"]

    rows = []
    import random
    random.seed(99)
    for i in range(1, 46):
        created = datetime(2025, 1, 15) + timedelta(days=random.randint(0, 180))
        due = created + timedelta(days=random.randint(5, 14))
        status = random.choice(statuses)
        rows.append({
            "RFI #": f"RFI-{i:04d}",
            "Subject": f"Clarification on {random.choice(disciplines)} detail #{random.randint(100,999)}",
            "Discipline": random.choice(disciplines),
            "Contractor": random.choice(contractors),
            "Status": status,
            "Priority": random.choice(priority),
            "Ball in Court": random.choice(["Consultant", "Contractor", "Owner", "Architect"]) if status != "Closed" else "Closed",
            "Date Created": created.strftime("%Y-%m-%d"),
            "Due Date": due.strftime("%Y-%m-%d"),
            "Date Closed": (due + timedelta(days=random.randint(-2, 7))).strftime("%Y-%m-%d") if status == "Closed" else "",
            "Days Open": (datetime.now() - created).days if status != "Closed" else (due - created).days + random.randint(-2, 5),
            "Cost Impact": random.choice(cost_impact),
            "Schedule Impact": random.choice(["Yes", "No"]),
        })
    return pd.DataFrame(rows)


# ============================================================
# DATA LOADING
# ============================================================
st.markdown(f"# 🏗️ Submittal & RFI Combined Dashboard")
st.markdown(f"<p style='color:{COLORS['muted']}; margin-top:-10px;'>API CPMC Project — Procore CSV Data Tracker</p>", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### 📁 Data Source")
    data_source = st.radio("Choose data source:", ["📊 Sample Data (Demo)", "📤 Upload Procore CSV"], label_visibility="collapsed")

    if data_source == "📤 Upload Procore CSV":
        st.markdown("---")
        st.markdown("**Upload Submittals CSV**")
        sub_file = st.file_uploader("Submittals", type=["csv"], key="sub", label_visibility="collapsed")
        st.markdown("**Upload RFIs CSV**")
        rfi_file = st.file_uploader("RFIs", type=["csv"], key="rfi", label_visibility="collapsed")
    else:
        sub_file = None
        rfi_file = None

    st.markdown("---")
    st.markdown("### ⚙️ Settings")
    submittal_threshold = st.slider("Submittal overdue threshold (days)", 5, 30, 14)
    rfi_threshold = st.slider("RFI overdue threshold (days)", 3, 21, 10)
    today = datetime.now()
    st.markdown(f"<p style='color:{COLORS['muted']}; font-size: 0.8rem;'>Report Date: {today.strftime('%B %d, %Y')}</p>", unsafe_allow_html=True)

# Load data
if data_source == "📤 Upload Procore CSV" and sub_file is not None:
    df_sub = pd.read_csv(sub_file)
    df_sub.columns = df_sub.columns.str.strip()
else:
    df_sub = generate_sample_submittals()

if data_source == "📤 Upload Procore CSV" and rfi_file is not None:
    df_rfi = pd.read_csv(rfi_file)
    df_rfi.columns = df_rfi.columns.str.strip()
else:
    df_rfi = generate_sample_rfis()

# Parse dates
for col in ["Date Created", "Due Date", "Date Closed"]:
    if col in df_sub.columns:
        df_sub[col] = pd.to_datetime(df_sub[col], errors="coerce")
    if col in df_rfi.columns:
        df_rfi[col] = pd.to_datetime(df_rfi[col], errors="coerce")

# Calculate overdue flags
df_sub["Is Overdue"] = (df_sub["Status"].isin(["Open", "Pending Review", "Revise & Resubmit"])) & \
                        (df_sub["Days Open"] > submittal_threshold)
df_rfi["Is Overdue"] = (df_rfi["Status"].isin(["Open", "Pending Response", "Overdue"])) & \
                        (df_rfi["Days Open"] > rfi_threshold)


# ============================================================
# SIDEBAR FILTERS
# ============================================================
with st.sidebar:
    st.markdown("### 🔍 Filters")
    contractors_all = sorted(set(df_sub["Contractor"].unique()) | set(df_rfi["Contractor"].unique()))
    sel_contractors = st.multiselect("Contractor", contractors_all, default=contractors_all)

    if "Discipline" in df_rfi.columns:
        disciplines_all = sorted(df_rfi["Discipline"].dropna().unique())
        sel_disciplines = st.multiselect("RFI Discipline", disciplines_all, default=disciplines_all)
    else:
        sel_disciplines = []

# Apply filters
df_sub_f = df_sub[df_sub["Contractor"].isin(sel_contractors)]
df_rfi_f = df_rfi[df_rfi["Contractor"].isin(sel_contractors)]
if sel_disciplines:
    df_rfi_f = df_rfi_f[df_rfi_f["Discipline"].isin(sel_disciplines)]


# ============================================================
# TOP-LEVEL METRICS
# ============================================================
def metric_card(label, value, color):
    return f"""
    <div class='metric-card'>
        <div class='metric-label'>{label}</div>
        <div class='metric-value' style='color:{color};'>{value}</div>
    </div>"""

st.markdown("<div class='section-header'>📊 Overview</div>", unsafe_allow_html=True)

col1, col2, col3, col4, col5, col6 = st.columns(6)
sub_open = df_sub_f[df_sub_f["Status"].isin(["Open", "Pending Review", "Revise & Resubmit"])].shape[0]
sub_closed = df_sub_f[df_sub_f["Status"].isin(["Approved", "Approved as Noted", "Rejected"])].shape[0]
sub_overdue = df_sub_f["Is Overdue"].sum()
rfi_open = df_rfi_f[df_rfi_f["Status"].isin(["Open", "Pending Response", "Overdue"])].shape[0]
rfi_closed = df_rfi_f[df_rfi_f["Status"] == "Closed"].shape[0]
rfi_overdue = df_rfi_f["Is Overdue"].sum()

with col1:
    st.markdown(metric_card("Submittals Open", sub_open, COLORS["warning"]), unsafe_allow_html=True)
with col2:
    st.markdown(metric_card("Submittals Closed", sub_closed, COLORS["success"]), unsafe_allow_html=True)
with col3:
    st.markdown(metric_card("Submittals Overdue", int(sub_overdue), COLORS["danger"]), unsafe_allow_html=True)
with col4:
    st.markdown(metric_card("RFIs Open", rfi_open, COLORS["blue"]), unsafe_allow_html=True)
with col5:
    st.markdown(metric_card("RFIs Closed", rfi_closed, COLORS["success"]), unsafe_allow_html=True)
with col6:
    st.markdown(metric_card("RFIs Overdue", int(rfi_overdue), COLORS["danger"]), unsafe_allow_html=True)


# ============================================================
# OVERDUE ALERTS
# ============================================================
overdue_subs = df_sub_f[df_sub_f["Is Overdue"]].sort_values("Days Open", ascending=False)
overdue_rfis = df_rfi_f[df_rfi_f["Is Overdue"]].sort_values("Days Open", ascending=False)

if len(overdue_subs) > 0 or len(overdue_rfis) > 0:
    st.markdown("<div class='section-header'>🚨 Overdue Alerts</div>", unsafe_allow_html=True)
    for _, row in overdue_subs.head(5).iterrows():
        st.markdown(
            f"<div class='alert-banner'>⚠️ <b>{row['Submittal #']}</b> — {row['Title']} | "
            f"Contractor: {row['Contractor']} | Ball in Court: {row['Ball in Court']} | "
            f"<b>{row['Days Open']} days open</b></div>",
            unsafe_allow_html=True
        )
    for _, row in overdue_rfis.head(5).iterrows():
        st.markdown(
            f"<div class='alert-banner'>⚠️ <b>{row['RFI #']}</b> — {row['Subject']} | "
            f"Contractor: {row['Contractor']} | Ball in Court: {row['Ball in Court']} | "
            f"<b>{row['Days Open']} days open</b></div>",
            unsafe_allow_html=True
        )


# ============================================================
# TABS: SUBMITTALS | RFIs | ANALYTICS
# ============================================================
tab1, tab2, tab3 = st.tabs(["📋 Submittals", "📝 RFIs", "📈 Analytics & Bottlenecks"])

PLOT_LAYOUT = dict(
    paper_bgcolor=COLORS["bg"],
    plot_bgcolor=COLORS["bg"],
    font=dict(color=COLORS["text"]),
    title_font_size=14,
    xaxis=dict(gridcolor=COLORS["grid"]),
    yaxis=dict(gridcolor=COLORS["grid"]),
)

# ---- SUBMITTALS TAB ----
with tab1:
    st.markdown("<div class='section-header'>Submittal Status Board</div>", unsafe_allow_html=True)

    col_a, col_b = st.columns(2)
    with col_a:
        fig_sub_status = px.pie(
            df_sub_f, names="Status", hole=0.5,
            color_discrete_sequence=[COLORS["warning"], COLORS["blue"], COLORS["success"],
                                      COLORS["accent"], COLORS["danger"], COLORS["accent2"]],
            title="Submittal Status Distribution"
        )
        fig_sub_status.update_layout(
            paper_bgcolor=COLORS["bg"], plot_bgcolor=COLORS["bg"],
            font=dict(color=COLORS["text"]), title_font_size=14,
            legend=dict(font=dict(size=11))
        )
        st.plotly_chart(fig_sub_status, use_container_width=True)

    with col_b:
        bic = df_sub_f[df_sub_f["Status"].isin(["Open", "Pending Review", "Revise & Resubmit"])]
        bic_counts = bic["Ball in Court"].value_counts().reset_index()
        bic_counts.columns = ["Ball in Court", "Count"]
        fig_bic = px.bar(
            bic_counts, x="Ball in Court", y="Count",
            color="Count", color_continuous_scale=["#E2E8F0", COLORS["accent"]],
            title="Open Submittals — Ball in Court"
        )
        fig_bic.update_layout(**PLOT_LAYOUT, showlegend=False)
        st.plotly_chart(fig_bic, use_container_width=True)

    # Contractor breakdown
    st.markdown("**Submittals by Contractor**")
    sub_contractor = df_sub_f.groupby(["Contractor", "Status"]).size().reset_index(name="Count")
    fig_sub_contr = px.bar(
        sub_contractor, x="Contractor", y="Count", color="Status", barmode="stack",
        color_discrete_sequence=[COLORS["warning"], COLORS["blue"], COLORS["success"],
                                  COLORS["accent"], COLORS["danger"], COLORS["accent2"]]
    )
    fig_sub_contr.update_layout(
        **PLOT_LAYOUT, legend=dict(orientation="h", y=-0.2)
    )
    st.plotly_chart(fig_sub_contr, use_container_width=True)

    # Full table
    st.markdown("**Full Submittal Log**")
    display_sub = df_sub_f.copy()
    display_sub["Date Created"] = display_sub["Date Created"].dt.strftime("%Y-%m-%d")
    display_sub["Due Date"] = display_sub["Due Date"].dt.strftime("%Y-%m-%d")
    display_sub["Date Closed"] = display_sub["Date Closed"].apply(
        lambda x: x.strftime("%Y-%m-%d") if pd.notna(x) else ""
    )
    st.dataframe(
        display_sub.drop(columns=["Is Overdue"]),
        use_container_width=True, height=400,
        column_config={"Days Open": st.column_config.ProgressColumn(
            "Days Open", min_value=0, max_value=int(df_sub_f["Days Open"].max()),
            format="%d days"
        )}
    )

# ---- RFI TAB ----
with tab2:
    st.markdown("<div class='section-header'>RFI Status Board</div>", unsafe_allow_html=True)

    col_c, col_d = st.columns(2)
    with col_c:
        fig_rfi_status = px.pie(
            df_rfi_f, names="Status", hole=0.5,
            color_discrete_sequence=[COLORS["warning"], COLORS["blue"], COLORS["success"], COLORS["danger"]],
            title="RFI Status Distribution"
        )
        fig_rfi_status.update_layout(
            paper_bgcolor=COLORS["bg"], plot_bgcolor=COLORS["bg"],
            font=dict(color=COLORS["text"]), title_font_size=14
        )
        st.plotly_chart(fig_rfi_status, use_container_width=True)

    with col_d:
        if "Discipline" in df_rfi_f.columns:
            disc_counts = df_rfi_f["Discipline"].value_counts().reset_index()
            disc_counts.columns = ["Discipline", "Count"]
            fig_disc = px.bar(
                disc_counts, x="Discipline", y="Count",
                color="Count", color_continuous_scale=["#E2E8F0", COLORS["accent2"]],
                title="RFIs by Discipline"
            )
            fig_disc.update_layout(**PLOT_LAYOUT, showlegend=False)
            st.plotly_chart(fig_disc, use_container_width=True)

    # Priority & Impact
    col_e, col_f = st.columns(2)
    with col_e:
        if "Priority" in df_rfi_f.columns:
            pri = df_rfi_f["Priority"].value_counts().reset_index()
            pri.columns = ["Priority", "Count"]
            fig_pri = px.bar(pri, x="Priority", y="Count",
                             color="Priority",
                             color_discrete_map={"Critical": COLORS["danger"], "High": COLORS["warning"],
                                                  "Medium": COLORS["blue"], "Low": COLORS["muted"]},
                             title="RFIs by Priority")
            fig_pri.update_layout(**PLOT_LAYOUT, showlegend=False)
            st.plotly_chart(fig_pri, use_container_width=True)

    with col_f:
        if "Cost Impact" in df_rfi_f.columns:
            cost = df_rfi_f["Cost Impact"].value_counts().reset_index()
            cost.columns = ["Cost Impact", "Count"]
            fig_cost = px.pie(cost, names="Cost Impact", values="Count", hole=0.5,
                              color_discrete_sequence=[COLORS["success"], COLORS["warning"], COLORS["danger"]],
                              title="RFI Cost Impact")
            fig_cost.update_layout(
                paper_bgcolor=COLORS["bg"], plot_bgcolor=COLORS["bg"],
                font=dict(color=COLORS["text"]), title_font_size=14
            )
            st.plotly_chart(fig_cost, use_container_width=True)

    # Full RFI table
    st.markdown("**Full RFI Log**")
    display_rfi = df_rfi_f.copy()
    display_rfi["Date Created"] = display_rfi["Date Created"].dt.strftime("%Y-%m-%d")
    display_rfi["Due Date"] = display_rfi["Due Date"].dt.strftime("%Y-%m-%d")
    display_rfi["Date Closed"] = display_rfi["Date Closed"].apply(
        lambda x: x.strftime("%Y-%m-%d") if pd.notna(x) else ""
    )
    st.dataframe(
        display_rfi.drop(columns=["Is Overdue"]),
        use_container_width=True, height=400,
        column_config={"Days Open": st.column_config.ProgressColumn(
            "Days Open", min_value=0, max_value=int(df_rfi_f["Days Open"].max()),
            format="%d days"
        )}
    )

# ---- ANALYTICS TAB ----
with tab3:
    st.markdown("<div class='section-header'>Bottleneck & Trend Analytics</div>", unsafe_allow_html=True)

    col_g, col_h = st.columns(2)
    with col_g:
        avg_sub = df_sub_f.groupby("Contractor")["Days Open"].mean().reset_index()
        avg_sub.columns = ["Contractor", "Avg Days"]
        avg_sub = avg_sub.sort_values("Avg Days", ascending=False)
        fig_avg_sub = px.bar(
            avg_sub, x="Contractor", y="Avg Days",
            color="Avg Days", color_continuous_scale=["#059669", "#D97706", "#DC2626"],
            title="Avg Submittal Turnaround by Contractor"
        )
        fig_avg_sub.update_layout(**PLOT_LAYOUT, showlegend=False)
        st.plotly_chart(fig_avg_sub, use_container_width=True)

    with col_h:
        avg_rfi = df_rfi_f.groupby("Contractor")["Days Open"].mean().reset_index()
        avg_rfi.columns = ["Contractor", "Avg Days"]
        avg_rfi = avg_rfi.sort_values("Avg Days", ascending=False)
        fig_avg_rfi = px.bar(
            avg_rfi, x="Contractor", y="Avg Days",
            color="Avg Days", color_continuous_scale=["#059669", "#D97706", "#DC2626"],
            title="Avg RFI Response Time by Contractor"
        )
        fig_avg_rfi.update_layout(**PLOT_LAYOUT, showlegend=False)
        st.plotly_chart(fig_avg_rfi, use_container_width=True)

    # Ball in Court heatmap
    st.markdown("**Ball in Court — Who's Holding Open Items?**")
    bic_sub = df_sub_f[~df_sub_f["Ball in Court"].isin(["Closed"])].groupby(
        ["Contractor", "Ball in Court"]).size().reset_index(name="Count")
    bic_rfi = df_rfi_f[~df_rfi_f["Ball in Court"].isin(["Closed"])].groupby(
        ["Contractor", "Ball in Court"]).size().reset_index(name="Count")
    bic_combined = pd.concat([
        bic_sub.assign(Type="Submittal"),
        bic_rfi.assign(Type="RFI")
    ])

    if not bic_combined.empty:
        fig_heat = px.treemap(
            bic_combined, path=["Ball in Court", "Contractor", "Type"], values="Count",
            color="Count", color_continuous_scale=["#E2E8F0", COLORS["danger"]],
            title="Open Items — Ball in Court Breakdown"
        )
        fig_heat.update_layout(
            paper_bgcolor=COLORS["bg"], font=dict(color=COLORS["text"]),
            title_font_size=14
        )
        st.plotly_chart(fig_heat, use_container_width=True)

    # Cumulative trend over time
    st.markdown("**Cumulative Open Items Over Time**")
    sub_created = df_sub_f.groupby(df_sub_f["Date Created"].dt.to_period("W").dt.start_time).size().cumsum().reset_index()
    sub_created.columns = ["Week", "Cumulative Submittals"]
    rfi_created = df_rfi_f.groupby(df_rfi_f["Date Created"].dt.to_period("W").dt.start_time).size().cumsum().reset_index()
    rfi_created.columns = ["Week", "Cumulative RFIs"]

    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(
        x=sub_created["Week"], y=sub_created["Cumulative Submittals"],
        mode="lines+markers", name="Submittals",
        line=dict(color=COLORS["accent"], width=2),
        marker=dict(size=5)
    ))
    fig_trend.add_trace(go.Scatter(
        x=rfi_created["Week"], y=rfi_created["Cumulative RFIs"],
        mode="lines+markers", name="RFIs",
        line=dict(color=COLORS["accent2"], width=2),
        marker=dict(size=5)
    ))
    fig_trend.update_layout(
        paper_bgcolor=COLORS["bg"], plot_bgcolor=COLORS["bg"],
        font=dict(color=COLORS["text"]),
        xaxis=dict(gridcolor=COLORS["grid"], title="Week"),
        yaxis=dict(gridcolor=COLORS["grid"], title="Count"),
        legend=dict(orientation="h", y=-0.15),
        height=350
    )
    st.plotly_chart(fig_trend, use_container_width=True)


# ============================================================
# EXPORT
# ============================================================
st.markdown("---")
st.markdown("### 📥 Export Reports")
col_x, col_y, col_z = st.columns(3)

with col_x:
    overdue_report = pd.concat([
        overdue_subs[["Submittal #", "Title", "Contractor", "Ball in Court", "Days Open"]].rename(
            columns={"Submittal #": "Item #", "Title": "Description"}),
        overdue_rfis[["RFI #", "Subject", "Contractor", "Ball in Court", "Days Open"]].rename(
            columns={"RFI #": "Item #", "Subject": "Description"})
    ])
    if not overdue_report.empty:
        csv_overdue = overdue_report.to_csv(index=False)
        st.download_button("⬇️ Overdue Items Report", csv_overdue, "overdue_report.csv", "text/csv")

with col_y:
    csv_sub = df_sub_f.drop(columns=["Is Overdue"]).to_csv(index=False)
    st.download_button("⬇️ Full Submittals CSV", csv_sub, "submittals_export.csv", "text/csv")

with col_z:
    csv_rfi = df_rfi_f.drop(columns=["Is Overdue"]).to_csv(index=False)
    st.download_button("⬇️ Full RFIs CSV", csv_rfi, "rfis_export.csv", "text/csv")

st.markdown(f"<p style='text-align:center; color:{COLORS['muted']}; margin-top:30px;'>API CPMC Project Dashboard | Bird Construction | Built with Streamlit</p>", unsafe_allow_html=True)
