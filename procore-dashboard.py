import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import io
import re

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
    .debug-box {{
        background: #F0FDF4;
        border: 1px solid #BBF7D0;
        border-radius: 8px;
        padding: 12px 16px;
        margin: 8px 0;
        font-size: 0.82rem;
        color: #166534;
    }}
</style>
""", unsafe_allow_html=True)


# ============================================================
# EMPLOYEE → COMPANY MAPPING
# ============================================================
EMPLOYEE_COMPANY_MAP = {
    "dan riske": "CIMA+",
    "jonathan garvey-wong": "CIMA+",
    "trent eklund": "SMP",
    "warren lesenko": "SMP",
    "robbie gray": "CRB",
    "saurav khanna": "CRB",
    "stephanie furukawa": "CRB",
    "andre-pierre ghys": "CRB",
    "tiffany tjong": "CRB",
    "gerry drouillard": "CRB",
    "vasyl zaiets": "API",
    "bernard gagnon": "API",
    "lesley woods": "Bird",
    "yvonne de la fuente": "Planworks",
    "andreas loutas": "Unknown",
}


def extract_companies_from_names(cell_value):
    if pd.isna(cell_value) or str(cell_value).strip() == "":
        return "Unknown"
    text = str(cell_value)
    companies = set()
    parts = re.split(r'[,\n]+', text)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        match = re.search(r'\(([^)]+)\)', part)
        if match:
            companies.add(match.group(1).strip())
            continue
        clean_name = re.sub(r'\([^)]*\)', '', part).strip().lower()
        if clean_name in EMPLOYEE_COMPANY_MAP:
            companies.add(EMPLOYEE_COMPANY_MAP[clean_name])
        else:
            found = False
            for emp_name, company in EMPLOYEE_COMPANY_MAP.items():
                if emp_name in clean_name or clean_name in emp_name:
                    companies.add(company)
                    found = True
                    break
            if not found and clean_name:
                companies.add("Unknown")
    if not companies:
        return "Unknown"
    if len(companies) > 1:
        companies.discard("Unknown")
    return ", ".join(sorted(companies))


# ============================================================
# PROCORE COLUMN NAME MAPPING
# ============================================================
SUBMITTAL_COL_MAP = {
    # Procore name variants → internal name
    "number": "Submittal #", "#": "Submittal #", "submittal #": "Submittal #",
    "submittal number": "Submittal #", "no.": "Submittal #", "no": "Submittal #",
    "title": "Title", "description": "Title", "submittal title": "Title",
    "specification section": "Spec Section", "spec section": "Spec Section",
    "spec #": "Spec Section", "spec": "Spec Section",
    "status": "Status", "current status": "Status", "workflow status": "Status",
    "ball in court": "Ball in Court", "ball-in-court": "Ball in Court",
    "responsible party": "Ball in Court", "current ball in court": "Ball in Court",
    "received from": "Received From", "submitted by": "Received From",
    "created by": "Received From", "originator": "Received From",
    "distributed to": "Reviewer", "reviewer": "Reviewer",
    "approver": "Reviewer", "assigned to": "Reviewer",
    "due date": "Due Date", "required on site": "Due Date",
    "required on-site date": "Due Date", "date required": "Due Date",
    "issue date": "Due Date", "needed by": "Due Date",
    "date created": "Date Created", "created at": "Date Created",
    "created date": "Date Created", "creation date": "Date Created",
    "submit date": "Date Created", "submitted date": "Date Created",
    "submitted on": "Date Created", "date submitted": "Date Created",
    "date opened": "Date Created", "opened": "Date Created",
    "closed date": "Date Closed", "date closed": "Date Closed",
    "closed": "Date Closed", "closed at": "Date Closed",
    "date returned": "Date Closed", "returned date": "Date Closed",
    "contractor": "Contractor", "company": "Contractor",
    "responsible contractor": "Contractor", "subcontractor": "Contractor",
    "trade": "Contractor", "vendor": "Contractor",
    "overdue": "Procore Overdue",
    "days open": "Days Open", "age": "Days Open", "days": "Days Open",
}

RFI_COL_MAP = {
    "number": "RFI #", "#": "RFI #", "rfi #": "RFI #",
    "rfi number": "RFI #", "no.": "RFI #", "no": "RFI #",
    "subject": "Subject", "title": "Subject", "description": "Subject",
    "question": "Subject", "rfi subject": "Subject",
    "status": "Status", "current status": "Status",
    "ball in court": "Ball in Court", "ball-in-court": "Ball in Court",
    "responsible party": "Ball in Court", "current ball in court": "Ball in Court",
    "received from": "Received From", "initiated by": "Received From",
    "created by": "Received From", "originator": "Received From",
    "assigned to": "Assigned To", "rfi manager": "Assigned To",
    "responsible": "Assigned To",
    "due date": "Due Date", "date due": "Due Date",
    "response due": "Due Date", "response due date": "Due Date",
    "date created": "Date Created", "created at": "Date Created",
    "created date": "Date Created", "creation date": "Date Created",
    "date initiated": "Date Created", "initiated date": "Date Created",
    "date opened": "Date Created", "opened": "Date Created",
    "closed date": "Date Closed", "date closed": "Date Closed",
    "closed": "Date Closed", "closed at": "Date Closed",
    "date answered": "Date Closed", "answered date": "Date Closed",
    "contractor": "Contractor", "company": "Contractor",
    "responsible contractor": "Contractor", "subcontractor": "Contractor",
    "trade": "Contractor", "vendor": "Contractor",
    "discipline": "Discipline", "category": "Discipline", "trade": "Discipline",
    "priority": "Priority", "urgency": "Priority",
    "cost impact": "Cost Impact", "cost code": "Cost Impact",
    "schedule impact": "Schedule Impact",
    "overdue": "Procore Overdue",
    "days open": "Days Open", "age": "Days Open", "days": "Days Open",
}


def map_columns(df, col_map):
    """Rename columns by matching against the Procore mapping table."""
    rename_dict = {}
    for col in df.columns:
        key = col.strip().lower()
        if key in col_map:
            target = col_map[key]
            if target not in rename_dict.values():
                rename_dict[col] = target
    df = df.rename(columns=rename_dict)
    return df, rename_dict


# ============================================================
# OPEN STATUS DETECTION (auto-detect from actual data)
# ============================================================
KNOWN_CLOSED_STATUSES = {
    "closed", "approved", "approved as noted", "rejected", "void", "voided",
    "cancelled", "canceled", "completed", "resolved", "withdrawn",
}
KNOWN_OPEN_STATUSES = {
    "open", "pending", "pending review", "pending response", "submitted",
    "in review", "draft", "revise & resubmit", "revise and resubmit",
    "resubmit", "overdue", "under review", "awaiting response",
}


def classify_statuses(df):
    """Auto-classify statuses into open/closed based on known patterns + date hints."""
    if "Status" not in df.columns:
        return [], []
    all_statuses = df["Status"].dropna().unique()
    open_list, closed_list = [], []

    for s in all_statuses:
        s_lower = str(s).strip().lower()
        if s_lower in KNOWN_CLOSED_STATUSES:
            closed_list.append(s)
        elif s_lower in KNOWN_OPEN_STATUSES:
            open_list.append(s)
        else:
            # Heuristic: if most rows with this status have a Date Closed, it's closed
            if "Date Closed" in df.columns:
                mask = df["Status"] == s
                has_closed = df.loc[mask, "Date Closed"].notna().mean()
                if has_closed > 0.7:
                    closed_list.append(s)
                else:
                    open_list.append(s)
            else:
                open_list.append(s)

    return open_list, closed_list


# ============================================================
# FILE PARSER — CSV, Excel, PDF
# ============================================================
SUPPORTED_TYPES = ["csv", "xlsx", "xls", "pdf"]


def parse_uploaded_file(uploaded_file):
    if uploaded_file is None:
        return None
    name = uploaded_file.name.lower()
    try:
        if name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        elif name.endswith((".xlsx", ".xls")):
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
                st.error("📦 `pdfplumber` required for PDF. Install: `pip install pdfplumber`")
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
            df = pd.DataFrame(all_rows[1:], columns=all_rows[0])
        else:
            st.error(f"Unsupported file type: {uploaded_file.name}")
            return None
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"❌ Error reading **{uploaded_file.name}**: {e}")
        return None


# ============================================================
# DERIVE CONTRACTOR FROM NAMES
# ============================================================
def derive_contractor_column(df):
    if "Contractor" in df.columns:
        sample = df["Contractor"].dropna().head(20).str.strip().str.lower()
        known = {"cima+", "smp", "crb", "api", "bird", "planworks", "icon electric"}
        if any(any(k in s for k in known) for s in sample):
            return df

    name_cols = []
    for col in df.columns:
        cl = col.lower()
        if any(kw in cl for kw in [
            "ball in court", "assigned", "responsible", "reviewer",
            "received from", "created by", "submitted by", "name",
            "distributed to", "approver", "rfi manager"
        ]):
            name_cols.append(col)

    if name_cols:
        source_col = name_cols[0]
        df["Contractor"] = df[source_col].apply(extract_companies_from_names)
        st.sidebar.success(f"✅ Mapped **'{source_col}'** → Contractor")
    elif "Contractor" not in df.columns:
        df["Contractor"] = "Unknown"
    return df


# ============================================================
# FULL NORMALIZATION
# ============================================================
def normalize_columns(df, item_type="submittal"):
    col_map = SUBMITTAL_COL_MAP if item_type == "submittal" else RFI_COL_MAP
    df, mapped = map_columns(df, col_map)

    # Derive Contractor from employee names
    df = derive_contractor_column(df)

    # Parse date columns
    for col in ["Date Created", "Due Date", "Date Closed"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # Auto-calculate Days Open
    if "Days Open" not in df.columns:
        if "Date Created" in df.columns:
            now = pd.Timestamp.now()
            if "Date Closed" in df.columns:
                end = df["Date Closed"].fillna(now)
            else:
                end = now
            df["Days Open"] = (end - df["Date Created"]).dt.days.clip(lower=0)
        else:
            df["Days Open"] = 0
    else:
        df["Days Open"] = pd.to_numeric(df["Days Open"], errors="coerce").fillna(0).astype(int)

    # Defaults for missing columns
    defaults = {"Status": "Open", "Contractor": "Unknown", "Ball in Court": "Unknown"}
    if item_type == "submittal":
        defaults.update({"Submittal #": "", "Title": "", "Reviewer": "", "Spec Section": ""})
    else:
        defaults.update({"RFI #": "", "Subject": "", "Discipline": "General",
                         "Priority": "Medium", "Cost Impact": "None", "Schedule Impact": "No"})
    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    # Map Ball in Court to companies if it has employee names
    if "Ball in Court" in df.columns:
        sample_bic = df["Ball in Court"].dropna().head(10).str.strip().str.lower()
        standard_bic = {"consultant", "contractor", "owner", "architect", "closed", "unknown", ""}
        if not any(s in standard_bic for s in sample_bic):
            df["Ball in Court"] = df["Ball in Court"].apply(extract_companies_from_names)

    return df


# ============================================================
# OVERDUE CALCULATION (flexible)
# ============================================================
def calculate_overdue(df, threshold_days, open_statuses):
    """
    Mark items as overdue using multiple signals:
    1. Procore's own 'Procore Overdue' flag (if present)
    2. Status is open AND days open > threshold
    3. Status is open AND due date has passed
    """
    is_open = df["Status"].isin(open_statuses)

    # Signal 1: Procore overdue flag
    procore_flag = pd.Series(False, index=df.index)
    if "Procore Overdue" in df.columns:
        procore_flag = df["Procore Overdue"].astype(str).str.strip().str.lower().isin(
            ["yes", "true", "1", "overdue", "y"]
        )

    # Signal 2: Days open exceeds threshold
    days_exceed = df["Days Open"] > threshold_days

    # Signal 3: Due date has passed
    past_due = pd.Series(False, index=df.index)
    if "Due Date" in df.columns:
        past_due = df["Due Date"].notna() & (df["Due Date"] < pd.Timestamp.now())

    # Overdue = open AND (any signal)
    df["Is Overdue"] = is_open & (procore_flag | days_exceed | past_due)
    return df


# ============================================================
# SAMPLE DATA GENERATORS
# ============================================================
def generate_sample_submittals():
    contractors = ["CRB", "CIMA+", "SMP", "Bird", "API"]
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
    contractors = ["CRB", "CIMA+", "SMP", "Bird", "API"]
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
# MAIN LAYOUT
# ============================================================
st.markdown("# 🏗️ Submittal & RFI Combined Dashboard")
st.markdown(f"<p style='color:{COLORS['muted']}; margin-top:-10px;'>API CPMC Project — Procore Data Tracker (CSV / Excel / PDF)</p>", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### 📁 Data Source")
    data_source = st.radio("Choose data source:", ["📊 Sample Data (Demo)", "📤 Upload File"], label_visibility="collapsed")

    if data_source == "📤 Upload File":
        st.markdown("---")
        st.caption("Supported: CSV, Excel (.xlsx/.xls), PDF")
        st.markdown("**Upload Submittals**")
        sub_file = st.file_uploader("Submittals", type=SUPPORTED_TYPES, key="sub", label_visibility="collapsed")
        st.markdown("**Upload RFIs**")
        rfi_file = st.file_uploader("RFIs", type=SUPPORTED_TYPES, key="rfi", label_visibility="collapsed")
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
if data_source == "📤 Upload File" and sub_file is not None:
    df_sub = parse_uploaded_file(sub_file)
    if df_sub is None:
        df_sub = generate_sample_submittals()
else:
    df_sub = generate_sample_submittals()

if data_source == "📤 Upload File" and rfi_file is not None:
    df_rfi = parse_uploaded_file(rfi_file)
    if df_rfi is None:
        df_rfi = generate_sample_rfis()
else:
    df_rfi = generate_sample_rfis()

# Normalize
df_sub = normalize_columns(df_sub, "submittal")
df_rfi = normalize_columns(df_rfi, "rfi")

# Auto-detect open/closed statuses
sub_open_statuses, sub_closed_statuses = classify_statuses(df_sub)
rfi_open_statuses, rfi_closed_statuses = classify_statuses(df_rfi)

# Calculate overdue
df_sub = calculate_overdue(df_sub, submittal_threshold, sub_open_statuses)
df_rfi = calculate_overdue(df_rfi, rfi_threshold, rfi_open_statuses)

# Show detected columns & statuses in sidebar (debug helper)
with st.sidebar:
    st.markdown("---")
    st.markdown("### 🔎 Detected Columns")
    with st.expander("Submittal columns"):
        st.caption(", ".join(df_sub.columns.tolist()))
        st.caption(f"**Open statuses:** {sub_open_statuses}")
        st.caption(f"**Closed statuses:** {sub_closed_statuses}")
    with st.expander("RFI columns"):
        st.caption(", ".join(df_rfi.columns.tolist()))
        st.caption(f"**Open statuses:** {rfi_open_statuses}")
        st.caption(f"**Closed statuses:** {rfi_closed_statuses}")

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
sub_open = df_sub_f[df_sub_f["Status"].isin(sub_open_statuses)].shape[0]
sub_closed = df_sub_f[df_sub_f["Status"].isin(sub_closed_statuses)].shape[0]
sub_overdue = df_sub_f["Is Overdue"].sum()
rfi_open = df_rfi_f[df_rfi_f["Status"].isin(rfi_open_statuses)].shape[0]
rfi_closed = df_rfi_f[df_rfi_f["Status"].isin(rfi_closed_statuses)].shape[0]
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

    id_col_sub = "Submittal #" if "Submittal #" in overdue_subs.columns else overdue_subs.columns[0]
    title_col_sub = "Title" if "Title" in overdue_subs.columns else (overdue_subs.columns[1] if len(overdue_subs.columns) > 1 else id_col_sub)

    for _, row in overdue_subs.head(5).iterrows():
        st.markdown(
            f"<div class='alert-banner'>⚠️ <b>{row[id_col_sub]}</b> — {row[title_col_sub]} | "
            f"Contractor: {row['Contractor']} | Ball in Court: {row['Ball in Court']} | "
            f"<b>{int(row['Days Open'])} days open</b></div>",
            unsafe_allow_html=True
        )

    id_col_rfi = "RFI #" if "RFI #" in overdue_rfis.columns else overdue_rfis.columns[0]
    title_col_rfi = "Subject" if "Subject" in overdue_rfis.columns else (overdue_rfis.columns[1] if len(overdue_rfis.columns) > 1 else id_col_rfi)

    for _, row in overdue_rfis.head(5).iterrows():
        st.markdown(
            f"<div class='alert-banner'>⚠️ <b>{row[id_col_rfi]}</b> — {row[title_col_rfi]} | "
            f"Contractor: {row['Contractor']} | Ball in Court: {row['Ball in Court']} | "
            f"<b>{int(row['Days Open'])} days open</b></div>",
            unsafe_allow_html=True
        )


# ============================================================
# TABS
# ============================================================
tab1, tab2, tab3 = st.tabs(["📋 Submittals", "📝 RFIs", "📈 Analytics & Bottlenecks"])

PLOT_LAYOUT = dict(
    paper_bgcolor=COLORS["bg"], plot_bgcolor=COLORS["bg"],
    font=dict(color=COLORS["text"]), title_font_size=14,
    xaxis=dict(gridcolor=COLORS["grid"]),
    yaxis=dict(gridcolor=COLORS["grid"]),
)

# ---- SUBMITTALS TAB ----
with tab1:
    st.markdown("<div class='section-header'>Submittal Status Board</div>", unsafe_allow_html=True)

    col_a, col_b = st.columns(2)
    with col_a:
        fig = px.pie(df_sub_f, names="Status", hole=0.5,
                     color_discrete_sequence=[COLORS["warning"], COLORS["blue"], COLORS["success"],
                                               COLORS["accent"], COLORS["danger"], COLORS["accent2"]],
                     title="Submittal Status Distribution")
        fig.update_layout(paper_bgcolor=COLORS["bg"], plot_bgcolor=COLORS["bg"],
                          font=dict(color=COLORS["text"]), title_font_size=14,
                          legend=dict(font=dict(size=11)))
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        bic = df_sub_f[df_sub_f["Status"].isin(sub_open_statuses)]
        if not bic.empty:
            bic_c = bic["Ball in Court"].value_counts().reset_index()
            bic_c.columns = ["Ball in Court", "Count"]
            fig = px.bar(bic_c, x="Ball in Court", y="Count",
                         color="Count", color_continuous_scale=["#E2E8F0", COLORS["accent"]],
                         title="Open Submittals — Ball in Court")
            fig.update_layout(**PLOT_LAYOUT, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Submittals by Contractor**")
    sub_contr = df_sub_f.groupby(["Contractor", "Status"]).size().reset_index(name="Count")
    fig = px.bar(sub_contr, x="Contractor", y="Count", color="Status", barmode="stack",
                 color_discrete_sequence=[COLORS["warning"], COLORS["blue"], COLORS["success"],
                                           COLORS["accent"], COLORS["danger"], COLORS["accent2"]])
    fig.update_layout(**PLOT_LAYOUT, legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Full Submittal Log**")
    display_sub = df_sub_f.copy()
    for dc in ["Date Created", "Due Date", "Date Closed"]:
        if dc in display_sub.columns and pd.api.types.is_datetime64_any_dtype(display_sub[dc]):
            display_sub[dc] = display_sub[dc].apply(lambda x: x.strftime("%Y-%m-%d") if pd.notna(x) else "")
    drop_cols = [c for c in ["Is Overdue", "Procore Overdue"] if c in display_sub.columns]
    st.dataframe(
        display_sub.drop(columns=drop_cols), use_container_width=True, height=400,
        column_config={"Days Open": st.column_config.ProgressColumn(
            "Days Open", min_value=0, max_value=max(int(df_sub_f["Days Open"].max()), 1), format="%d days"
        )}
    )

# ---- RFI TAB ----
with tab2:
    st.markdown("<div class='section-header'>RFI Status Board</div>", unsafe_allow_html=True)

    col_c, col_d = st.columns(2)
    with col_c:
        fig = px.pie(df_rfi_f, names="Status", hole=0.5,
                     color_discrete_sequence=[COLORS["warning"], COLORS["blue"], COLORS["success"], COLORS["danger"]],
                     title="RFI Status Distribution")
        fig.update_layout(paper_bgcolor=COLORS["bg"], plot_bgcolor=COLORS["bg"],
                          font=dict(color=COLORS["text"]), title_font_size=14)
        st.plotly_chart(fig, use_container_width=True)

    with col_d:
        if "Discipline" in df_rfi_f.columns:
            dc = df_rfi_f["Discipline"].value_counts().reset_index()
            dc.columns = ["Discipline", "Count"]
            fig = px.bar(dc, x="Discipline", y="Count",
                         color="Count", color_continuous_scale=["#E2E8F0", COLORS["accent2"]],
                         title="RFIs by Discipline")
            fig.update_layout(**PLOT_LAYOUT, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    col_e, col_f = st.columns(2)
    with col_e:
        if "Priority" in df_rfi_f.columns:
            pri = df_rfi_f["Priority"].value_counts().reset_index()
            pri.columns = ["Priority", "Count"]
            fig = px.bar(pri, x="Priority", y="Count", color="Priority",
                         color_discrete_map={"Critical": COLORS["danger"], "High": COLORS["warning"],
                                              "Medium": COLORS["blue"], "Low": COLORS["muted"]},
                         title="RFIs by Priority")
            fig.update_layout(**PLOT_LAYOUT, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    with col_f:
        if "Cost Impact" in df_rfi_f.columns:
            cost = df_rfi_f["Cost Impact"].value_counts().reset_index()
            cost.columns = ["Cost Impact", "Count"]
            fig = px.pie(cost, names="Cost Impact", values="Count", hole=0.5,
                         color_discrete_sequence=[COLORS["success"], COLORS["warning"], COLORS["danger"]],
                         title="RFI Cost Impact")
            fig.update_layout(paper_bgcolor=COLORS["bg"], plot_bgcolor=COLORS["bg"],
                              font=dict(color=COLORS["text"]), title_font_size=14)
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Full RFI Log**")
    display_rfi = df_rfi_f.copy()
    for dc in ["Date Created", "Due Date", "Date Closed"]:
        if dc in display_rfi.columns and pd.api.types.is_datetime64_any_dtype(display_rfi[dc]):
            display_rfi[dc] = display_rfi[dc].apply(lambda x: x.strftime("%Y-%m-%d") if pd.notna(x) else "")
    drop_cols = [c for c in ["Is Overdue", "Procore Overdue"] if c in display_rfi.columns]
    st.dataframe(
        display_rfi.drop(columns=drop_cols), use_container_width=True, height=400,
        column_config={"Days Open": st.column_config.ProgressColumn(
            "Days Open", min_value=0, max_value=max(int(df_rfi_f["Days Open"].max()), 1), format="%d days"
        )}
    )

# ---- ANALYTICS TAB ----
with tab3:
    st.markdown("<div class='section-header'>Bottleneck & Trend Analytics</div>", unsafe_allow_html=True)

    col_g, col_h = st.columns(2)
    with col_g:
        avg = df_sub_f.groupby("Contractor")["Days Open"].mean().reset_index()
        avg.columns = ["Contractor", "Avg Days"]
        avg = avg.sort_values("Avg Days", ascending=False)
        fig = px.bar(avg, x="Contractor", y="Avg Days",
                     color="Avg Days", color_continuous_scale=["#059669", "#D97706", "#DC2626"],
                     title="Avg Submittal Turnaround by Contractor")
        fig.update_layout(**PLOT_LAYOUT, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col_h:
        avg = df_rfi_f.groupby("Contractor")["Days Open"].mean().reset_index()
        avg.columns = ["Contractor", "Avg Days"]
        avg = avg.sort_values("Avg Days", ascending=False)
        fig = px.bar(avg, x="Contractor", y="Avg Days",
                     color="Avg Days", color_continuous_scale=["#059669", "#D97706", "#DC2626"],
                     title="Avg RFI Response Time by Contractor")
        fig.update_layout(**PLOT_LAYOUT, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Ball in Court — Who's Holding Open Items?**")
    bic_sub = df_sub_f[~df_sub_f["Ball in Court"].isin(["Closed", ""])].groupby(
        ["Contractor", "Ball in Court"]).size().reset_index(name="Count")
    bic_rfi = df_rfi_f[~df_rfi_f["Ball in Court"].isin(["Closed", ""])].groupby(
        ["Contractor", "Ball in Court"]).size().reset_index(name="Count")
    bic_all = pd.concat([bic_sub.assign(Type="Submittal"), bic_rfi.assign(Type="RFI")])

    if not bic_all.empty:
        fig = px.treemap(bic_all, path=["Ball in Court", "Contractor", "Type"], values="Count",
                         color="Count", color_continuous_scale=["#E2E8F0", COLORS["danger"]],
                         title="Open Items — Ball in Court Breakdown")
        fig.update_layout(paper_bgcolor=COLORS["bg"], font=dict(color=COLORS["text"]), title_font_size=14)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Cumulative Open Items Over Time**")
    fig_trend = go.Figure()
    if "Date Created" in df_sub_f.columns and df_sub_f["Date Created"].notna().any():
        sc = df_sub_f.dropna(subset=["Date Created"]).groupby(
            df_sub_f["Date Created"].dropna().dt.to_period("W").dt.start_time
        ).size().cumsum().reset_index()
        sc.columns = ["Week", "Cumulative Submittals"]
        fig_trend.add_trace(go.Scatter(x=sc["Week"], y=sc["Cumulative Submittals"],
                                        mode="lines+markers", name="Submittals",
                                        line=dict(color=COLORS["accent"], width=2), marker=dict(size=5)))

    if "Date Created" in df_rfi_f.columns and df_rfi_f["Date Created"].notna().any():
        rc = df_rfi_f.dropna(subset=["Date Created"]).groupby(
            df_rfi_f["Date Created"].dropna().dt.to_period("W").dt.start_time
        ).size().cumsum().reset_index()
        rc.columns = ["Week", "Cumulative RFIs"]
        fig_trend.add_trace(go.Scatter(x=rc["Week"], y=rc["Cumulative RFIs"],
                                        mode="lines+markers", name="RFIs",
                                        line=dict(color=COLORS["accent2"], width=2), marker=dict(size=5)))

    fig_trend.update_layout(
        paper_bgcolor=COLORS["bg"], plot_bgcolor=COLORS["bg"], font=dict(color=COLORS["text"]),
        xaxis=dict(gridcolor=COLORS["grid"], title="Week"),
        yaxis=dict(gridcolor=COLORS["grid"], title="Count"),
        legend=dict(orientation="h", y=-0.15), height=350
    )
    st.plotly_chart(fig_trend, use_container_width=True)


# ============================================================
# EXPORT
# ============================================================
st.markdown("---")
st.markdown("### 📥 Export Reports")
col_x, col_y, col_z = st.columns(3)

with col_x:
    sub_id = "Submittal #" if "Submittal #" in overdue_subs.columns else overdue_subs.columns[0] if not overdue_subs.empty else "Item"
    sub_title = "Title" if "Title" in overdue_subs.columns else (overdue_subs.columns[1] if len(overdue_subs.columns) > 1 and not overdue_subs.empty else "Description")
    rfi_id = "RFI #" if "RFI #" in overdue_rfis.columns else overdue_rfis.columns[0] if not overdue_rfis.empty else "Item"
    rfi_title = "Subject" if "Subject" in overdue_rfis.columns else (overdue_rfis.columns[1] if len(overdue_rfis.columns) > 1 and not overdue_rfis.empty else "Description")

    parts = []
    if not overdue_subs.empty:
        parts.append(overdue_subs[[sub_id, sub_title, "Contractor", "Ball in Court", "Days Open"]].rename(
            columns={sub_id: "Item #", sub_title: "Description"}))
    if not overdue_rfis.empty:
        parts.append(overdue_rfis[[rfi_id, rfi_title, "Contractor", "Ball in Court", "Days Open"]].rename(
            columns={rfi_id: "Item #", rfi_title: "Description"}))
    if parts:
        overdue_report = pd.concat(parts)
        st.download_button("⬇️ Overdue Items Report", overdue_report.to_csv(index=False), "overdue_report.csv", "text/csv")

with col_y:
    drop_c = [c for c in ["Is Overdue", "Procore Overdue"] if c in df_sub_f.columns]
    st.download_button("⬇️ Full Submittals CSV", df_sub_f.drop(columns=drop_c).to_csv(index=False), "submittals_export.csv", "text/csv")

with col_z:
    drop_c = [c for c in ["Is Overdue", "Procore Overdue"] if c in df_rfi_f.columns]
    st.download_button("⬇️ Full RFIs CSV", df_rfi_f.drop(columns=drop_c).to_csv(index=False), "rfis_export.csv", "text/csv")

st.markdown(f"<p style='text-align:center; color:{COLORS['muted']}; margin-top:30px;'>API CPMC Project Dashboard | Bird Construction | Built with Streamlit</p>", unsafe_allow_html=True)
