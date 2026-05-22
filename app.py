import os
import re
import time
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# -----------------------------
# Configuration
# -----------------------------
APP_TITLE = "IntelliLead — AI Lead Intelligence"
APP_ICON = "🧠"
DB_DIR = "data"
DB_PATH = os.path.join(DB_DIR, "leads.db")

st.set_page_config(page_title=APP_TITLE, layout="wide")


# -----------------------------
# Branding & Styling
# -----------------------------

def _inject_styles() -> None:
    st.markdown(
        """
        <style>
          .bb-page-title { font-size: 30px; font-weight: 900; margin-top: 6px; letter-spacing: -0.02em; }
          .bb-subtitle { color: #6b7280; font-size: 14px; }
          .bb-pill { display:inline-block; padding: 6px 10px; border-radius: 999px; background: rgba(99,102,241,0.16); border: 1px solid rgba(99,102,241,0.35); font-size: 12px; font-weight: 700; color: #c7d2fe; }

          .bb-status-badge { display:inline-block; padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 800; }
          .bb-status-pending { background: rgba(59,130,246,0.18); border: 1px solid rgba(59,130,246,0.45); color: #93c5fd; }
          .bb-status-completed { background: rgba(16,185,129,0.18); border: 1px solid rgba(16,185,129,0.45); color: #6ee7b7; }
          .bb-status-failed { background: rgba(239,68,68,0.18); border: 1px solid rgba(239,68,68,0.45); color: #fca5a5; }

          .bb-section { border-radius: 14px; border: 1px solid rgba(255,255,255,0.12); background: rgba(15,23,42,0.55); padding: 14px 14px; }
          .stApp { background-color: #0b1220; }
          .stMarkdown, .stText, label, .css-1y4p8pa { color: #e5e7eb; }
          div[data-testid="stForm"], div[data-testid="st-expander"], div[data-testid="stSelectbox"], div[data-testid="stTextInput"], div[data-testid="stTextArea"], div[data-testid="stDataFrame"], div[data-testid="stTable"], div[data-testid="stRadio"] { background-color: rgba(15,23,42,0.35); }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _brand_top_nav() -> None:
    left, right = st.columns([1.05, 1], gap="large")

    with left:
        st.markdown(
            f"""
            <div style="display:flex; align-items:center; gap:12px;">
              <div style="width:44px; height:44px; border-radius:14px; background: rgba(99,102,241,0.14); display:flex; align-items:center; justify-content:center; font-size:22px;">
                {APP_ICON}
              </div>
              <div>
                <div class="bb-page-title" style="font-size:26px; margin:0;">IntelliLead</div>
                <div class="bb-subtitle" style="margin-top:4px;">Smart lead capture · AI assistant · Automation workflows</div>
              </div>
            </div>
            <div style="margin-top:10px; display:flex; gap:8px; flex-wrap:wrap;">
              <span class="bb-pill">Streamlit</span>
              <span class="bb-pill">SQLite</span>
              <span class="bb-pill">AI automation</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with right:
        tabs = ["Dashboard", "Leads", "Chat", "Settings"]

        if "active_tab" not in st.session_state:
            st.session_state.active_tab = "Dashboard"

        # Deterministic tab navigation: use radio to set active tab reliably.
        tab_choice = st.radio(
            "",
            options=tabs,
            index=tabs.index(st.session_state.active_tab) if st.session_state.active_tab in tabs else 0,
            horizontal=True,
            key="top_nav_radio",
        )
        st.session_state.active_tab = tab_choice



# -----------------------------
# Persistence (SQLite)
# -----------------------------

def ensure_db() -> None:
    """Ensure the SQLite database and base table exist."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            department TEXT,
            message TEXT,
            created_at TEXT NOT NULL,
            automation_status TEXT NOT NULL DEFAULT 'pending',
            chatbot_last_reply TEXT
        )
        """
    )

    # Add new columns (ALTER TABLE IF NOT EXISTS pattern)
    _ensure_column(conn, cur, "urgency", "TEXT DEFAULT 'Just browsing'")
    _ensure_column(conn, cur, "priority", "TEXT DEFAULT 'Low'")
    _ensure_column(conn, cur, "ai_replies_count", "INTEGER DEFAULT 0")

    conn.commit()
    conn.close()


def _ensure_column(conn: sqlite3.Connection, cur: sqlite3.Cursor, column: str, column_def: str) -> None:
    """Add a column if it doesn't already exist."""
    cur.execute("PRAGMA table_info(leads)")
    existing = {row[1] for row in cur.fetchall()}
    if column not in existing:
        cur.execute(f"ALTER TABLE leads ADD COLUMN {column} {column_def}")


def check_duplicate_email(email: str) -> bool:
    """Return True if the given email already exists in the leads table."""
    ensure_db()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM leads WHERE email = ? LIMIT 1", (email.strip(),))
    row = cur.fetchone()
    conn.close()
    return row is not None


def _validate_email(email: str) -> bool:
    """Validate email with a simple regex."""
    # Simple email regex suitable for UI validation
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()) is not None


def insert_lead(
    name: str,
    email: str,
    phone: str,
    department: str,
    message: str,
    urgency: str,
    priority: str,
) -> int:
    """Insert a lead and return the new lead ID."""
    ensure_db()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    created_at = datetime.utcnow().isoformat() + "Z"
    cur.execute(
        """
        INSERT INTO leads (
            name, email, phone, department, message, created_at,
            urgency, priority
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (name, email, phone, department, message, created_at, urgency, priority),
    )
    lead_id = int(cur.lastrowid)
    conn.commit()
    conn.close()
    return lead_id


def set_automation_status(lead_id: int, status: str, chatbot_reply: Optional[str] = None) -> None:
    """Update automation status and optionally store chatbot last reply."""
    ensure_db()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    if chatbot_reply is not None:
        cur.execute(
            "UPDATE leads SET automation_status = ?, chatbot_last_reply = ? WHERE id = ?",
            (status, chatbot_reply, lead_id),
        )
    else:
        cur.execute("UPDATE leads SET automation_status = ? WHERE id = ?", (status, lead_id))
    conn.commit()
    conn.close()


def increment_ai_replies_count(lead_id: int) -> None:
    """Increment ai_replies_count for a lead."""
    ensure_db()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE leads SET ai_replies_count = COALESCE(ai_replies_count, 0) + 1 WHERE id = ?", (lead_id,))
    conn.commit()
    conn.close()


@st.cache_data(ttl=30)
def list_leads() -> pd.DataFrame:
    """List leads ordered by newest first."""
    ensure_db()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM leads ORDER BY id DESC", conn)
    conn.close()
    return df


@st.cache_data(ttl=30)
def get_leads_per_day(days: int = 7) -> List[Dict[str, Any]]:
    """Return leads grouped by date for the last `days` days."""
    ensure_db()
    conn = sqlite3.connect(DB_PATH)

    end = datetime.utcnow().date()
    start = end - timedelta(days=days - 1)

    df = pd.read_sql_query(
        """
        SELECT date(created_at) AS day, COUNT(*) AS count
        FROM leads
        WHERE date(created_at) >= ? AND date(created_at) <= ?
        GROUP BY day
        ORDER BY day ASC
        """,
        conn,
        params=(start.isoformat(), end.isoformat()),
    )
    conn.close()

    # Fill missing days
    day_to_count = {str(r["day"]): int(r["count"]) for _, r in df.iterrows()}

    out: List[Dict[str, Any]] = []
    for i in range(days):
        d = start + timedelta(days=i)
        out.append({"day": d.isoformat(), "count": day_to_count.get(d.isoformat(), 0)})
    return out


@st.cache_data(ttl=30)
def get_department_breakdown() -> Dict[str, int]:
    """Return department breakdown counts."""
    ensure_db()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        """
        SELECT COALESCE(department, 'Unknown') AS department, COUNT(*) AS count
        FROM leads
        GROUP BY department
        """,
        conn,
    )
    conn.close()
    return {str(r["department"]): int(r["count"]) for _, r in df.iterrows()}


@st.cache_data(ttl=30)
def get_kpi_counts() -> Dict[str, int]:
    """Compute dashboard KPI counts."""
    ensure_db()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        """
        SELECT
          COUNT(*) AS total,
          SUM(CASE WHEN automation_status='completed' THEN 1 ELSE 0 END) AS automated,
          SUM(CASE WHEN automation_status!='completed' THEN 1 ELSE 0 END) AS pending,
          SUM(CASE WHEN COALESCE(ai_replies_count,0) > 0 THEN 1 ELSE 0 END) AS ai_replies_sent
        FROM leads
        """,
        conn,
    )
    conn.close()
    row = df.iloc[0].to_dict()
    return {
        "total": int(row["total"] or 0),
        "automated": int(row["automated"] or 0),
        "pending": int(row["pending"] or 0),
        "ai_replies_sent": int(row["ai_replies_sent"] or 0),
    }


def get_ai_replies_sent_count_for_day(target_date: date) -> int:
    """Count leads created on target_date that have ai_replies_count > 0."""
    ensure_db()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        """
        SELECT COUNT(*) AS c
        FROM leads
        WHERE date(created_at) = ?
          AND COALESCE(ai_replies_count,0) > 0
        """,
        conn,
        params=(target_date.isoformat(),),
    )
    conn.close()
    return int(df.iloc[0]["c"] or 0)


def get_total_leads_for_day(target_date: date) -> int:
    """Count total leads created on target_date."""
    ensure_db()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        """
        SELECT COUNT(*) AS c
        FROM leads
        WHERE date(created_at) = ?
        """,
        conn,
        params=(target_date.isoformat(),),
    )
    conn.close()
    return int(df.iloc[0]["c"] or 0)


def get_automated_for_day(target_date: date) -> int:
    """Count automated (completed) leads created on target_date."""
    ensure_db()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        """
        SELECT COUNT(*) AS c
        FROM leads
        WHERE date(created_at) = ?
          AND automation_status='completed'
        """,
        conn,
        params=(target_date.isoformat(),),
    )
    conn.close()
    return int(df.iloc[0]["c"] or 0)


def get_pending_for_day(target_date: date) -> int:
    """Count pending leads created on target_date."""
    ensure_db()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        """
        SELECT COUNT(*) AS c
        FROM leads
        WHERE date(created_at) = ?
          AND (automation_status!='completed' OR automation_status IS NULL)
        """,
        conn,
        params=(target_date.isoformat(),),
    )
    conn.close()
    return int(df.iloc[0]["c"] or 0)


# -----------------------------
# "Free AI" responder (no API key required)
# -----------------------------

BUSINESS_KB: Dict[str, Dict[str, Any]] = {
    "admissions": {
        "q_keywords": ["admission", "apply", "apply now", "eligibility", "requirements"],
        "answer": "To apply: submit your details via the form, be ready for an interview round, and note that eligibility depends on the program requirements. Our team can confirm specifics after you submit.",
    },
    "pricing": {
        "q_keywords": ["fee", "pricing", "cost", "scholarship", "payment", "installment"],
        "answer": "For fee & scholarship options, share your department/program interest in the lead form. Our team will respond with the latest pricing, schedules, and available discounts.",
    },
    "course_structure": {
        "q_keywords": ["course", "syllabus", "curriculum", "modules", "structure", "what you learn"],
        "answer": "Our programs typically include structured learning modules, hands-on projects, and real-world automation workflows. Submit the form to receive the exact curriculum and learning outcomes for your track.",
    },
    "duration": {
        "q_keywords": ["duration", "how long", "weeks", "months", "timeline"],
        "answer": "Program duration depends on the track. After you submit your interest, we’ll share the exact duration, weekly schedule, and expected time commitment so you can plan ahead.",
    },
    "batch_timings": {
        "q_keywords": ["batch", "timing", "schedule", "class timing", "hours", "when"],
        "answer": "Batch timings vary by cohort. Share your interest via the lead form and our team will confirm upcoming batch start dates and session timings.",
    },
    "placement_support": {
        "q_keywords": ["placement", "job", "hiring", "interview support", "resume", "portfolio"],
        "answer": "We provide placement support including interview preparation and guidance on strengthening your portfolio. Submit the form and we’ll share the support process and how we help you move toward roles in your domain.",
    },
    "certification": {
        "q_keywords": ["certificate", "certification", "credential", "proof", "completion"],
        "answer": "Yes—program participants typically receive a certification upon successful completion. After you submit, we’ll confirm the certification details and eligibility requirements for your track.",
    },
    "refund_policy": {
        "q_keywords": ["refund", "cancellation", "policy", "return", "money back"],
        "answer": "Refund policies depend on the enrollment stage and program terms. Submit your details in the lead form and our team will share the refund/cancellation terms applicable to your situation.",
    },
}


def _detect_enroll_intent(user_text: str) -> bool:
    t = (user_text or "").lower()
    return "enroll" in t or "join now" in t


def generate_ai_reply(user_text: str) -> str:
    """Generate a chatbot reply using keyword matching."""
    text = (user_text or "").strip().lower()
    if not text:
        return "Please type a question and I’ll respond."

    for topic, item in BUSINESS_KB.items():
        if any(kw in text for kw in item["q_keywords"]):
            reply = item["answer"]
            break
    else:
        reply = (
            "Thanks for your question. I can help with admissions, pricing, course structure, duration, batch timings, placement support, certification, and refund policy. "
            "If you share your department/program interest via the lead form, I can tailor the next steps for you."
        )

    persona_prefix = "Hi, I'm IntelliLead AI — your smart assistant. "

    if _detect_enroll_intent(user_text):
        reply += " Ready to take the next step? Fill the lead form and our team will reach out within 24 hours."

    return persona_prefix + reply


# -----------------------------
# Automation workflow
# -----------------------------


def run_automation_for_lead(lead_id: int, lead_email: str, chatbot_prompt: str) -> Tuple[str, str]:
    """Simulate automation steps and update DB status + chatbot reply."""
    time.sleep(0.6)

    ack = "Received. Our team will contact you shortly."
    ai_reply = generate_ai_reply(chatbot_prompt)

    # increment ai replies
    increment_ai_replies_count(lead_id)

    set_automation_status(lead_id, status="completed", chatbot_reply=ai_reply)

    # simulate sending email
    print(f"[IntelliLead EMAIL] Sending confirmation to {lead_email} — lead #{lead_id}")

    return ack, ai_reply


# -----------------------------
# UI Sections
# -----------------------------


def render_dashboard() -> None:
    st.markdown(
        """
        <div class="bb-section">
          <h3 style="margin:0 0 8px 0;">Dashboard</h3>
          <div style="color:#cbd5e1; font-size:14px;">KPI metrics + leads trends + department breakdown</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # KPIs
    today = datetime.utcnow().date()
    yesterday = today - timedelta(days=1)

    totals = get_kpi_counts()

    # Today vs yesterday deltas (avoid crash if prior data missing)
    try:
        total_today = get_total_leads_for_day(today)
        total_yday = get_total_leads_for_day(yesterday)
        total_delta = total_today - total_yday
    except Exception:
        total_delta = 0

    try:
        automated_today = get_automated_for_day(today)
        automated_yday = get_automated_for_day(yesterday)
        automated_delta = automated_today - automated_yday
    except Exception:
        automated_delta = 0

    try:
        pending_today = get_pending_for_day(today)
        pending_yday = get_pending_for_day(yesterday)
        pending_delta = pending_today - pending_yday
    except Exception:
        pending_delta = 0

    try:
        ai_today = get_ai_replies_sent_count_for_day(today)
        ai_yday = get_ai_replies_sent_count_for_day(yesterday)
        ai_delta = ai_today - ai_yday
    except Exception:
        ai_delta = 0

    kpi_cols = st.columns(4, gap="large")
    kpi_defs = [
        ("Total Leads", totals["total"], total_delta),
        ("Automated", totals["automated"], automated_delta),
        ("Pending", totals["pending"], pending_delta),
        ("AI Replies sent", totals["ai_replies_sent"], ai_delta),
    ]

    for col, (label, value, delta) in zip(kpi_cols, kpi_defs):
        with col:
            col.metric(label, value, delta=delta)

    st.divider()

    # Charts
    chart_cols = st.columns([1.05, 0.95], gap="large")

    with chart_cols[0]:
        st.markdown(
            """
            <div class="bb-section" style="margin-bottom:12px;">
              <h3 style="margin:0 0 8px 0;">Leads per day (last 7 days)</h3>
              <div style="color:#cbd5e1; font-size:14px;">Trend of new lead submissions</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        series = get_leads_per_day(7)
        df = pd.DataFrame(series)
        if df.empty:
            st.info("No lead data yet.")
        else:
            # bar_chart expects columns: x-axis via index; easiest: set day as index
            df_chart = df.set_index("day")
            st.bar_chart(df_chart["count"])

    with chart_cols[1]:
        st.markdown(
            """
            <div class="bb-section" style="margin-bottom:12px;">
              <h3 style="margin:0 0 8px 0;">Department breakdown</h3>
              <div style="color:#cbd5e1; font-size:14px;">Donut chart by program interest</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        breakdown = get_department_breakdown()
        if not breakdown:
            st.info("No department data yet.")
        else:
            labels = list(breakdown.keys())
            values = list(breakdown.values())

            fig = go.Figure(
                data=[
                    go.Pie(
                        labels=labels,
                        values=values,
                        hole=0.55,
                        textinfo="percent+label",
                    )
                ]
            )
            fig.update_layout(
                margin=dict(l=10, r=10, t=10, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e5e7eb"),
                legend=dict(font=dict(color="#e5e7eb")),
            )
            st.plotly_chart(fig, use_container_width=True)


def render_leads_form() -> None:
    st.markdown(
        """
        <div class="bb-section">
          <h3 style="margin:0 0 8px 0;">Lead Capture</h3>
          <div style="color:#cbd5e1; font-size:14px;">Capture program interest and trigger automation workflows</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("Submit your details")

    with st.form("lead_form", clear_on_submit=True):
        name = st.text_input("Full Name")
        email = st.text_input("Email")
        phone = st.text_input("Phone (optional)")
        department = st.selectbox(
            "Program Interest",
            [
                "AI/Automation",
                "Data Science",
                "Full Stack",
                "Cloud Ops",
                "Other",
            ],
        )
        message = st.text_area("Message (optional)", placeholder="Tell us what you’re looking for...")
        urgency = st.radio(
            "Urgency",
            ["Just browsing", "Interested", "Ready to enroll"],
            horizontal=True,
        )

        submitted = st.form_submit_button("Submit Lead")

    if submitted:
        if not name.strip() or not email.strip():
            st.error("Name and Email are required.")
            return
        if not _validate_email(email):
            st.error("Please enter a valid email address.")
            return

        # Duplicate email check
        if check_duplicate_email(email.strip()):
            st.warning("This email already exists in the system. Your lead was not inserted.")
            return

        # Priority mapping
        if urgency == "Ready to enroll":
            priority = "High"
        elif urgency == "Interested":
            priority = "Medium"
        else:
            priority = "Low"

        lead_id = insert_lead(
            name=name.strip(),
            email=email.strip(),
            phone=phone.strip(),
            department=department.strip(),
            message=message.strip(),
            urgency=urgency,
            priority=priority,
        )

        st.balloons()
        st.success("Lead captured successfully!")

        # Automation timeline after form submit
        with st.status("Starting automation...", expanded=True) as status:
            status.update(label="Step 1: Lead saved to database ✅", state="complete")
            time.sleep(0.4)

            # AI reply generation
            chatbot_prompt = f"lead submission: {department}, urgency={urgency}. {message}".strip()
            ack, ai_reply = run_automation_for_lead(lead_id, email.strip(), chatbot_prompt)
            status.update(label="Step 2: AI reply generated ✅", state="complete")
            time.sleep(0.35)

            # workflow completed
            status.update(label='Step 3: Workflow completed — status set to "completed" ✅', state="complete")

        st.toast("Automation workflow executed", icon="✅")
        st.info(f"Automation acknowledgment: {ack}")
        st.session_state["current_lead_id"] = lead_id

        st.session_state["last_ai_reply"] = ai_reply


def render_chatbot() -> None:
    st.markdown(
        """
        <div class="bb-section">
          <h3 style="margin:0 0 8px 0;">AI Assistant</h3>
          <div style="color:#cbd5e1; font-size:14px;">Smart questions with lead-aware AI reply tracking</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("Ask business/course-related questions. Replies use an offline keyword-based responder (free fallback).")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    if "current_lead_id" not in st.session_state:
        st.session_state.current_lead_id = None

    # Clear chat button above chat input
    clear_col1, clear_col2 = st.columns([0.7, 0.3])
    with clear_col2:
        if st.button("Clear chat", key="clear_chat"):
            st.session_state.chat_history = []
            st.session_state.pop("last_ai_reply", None)

    for role, msg in st.session_state.chat_history:
        with st.chat_message(role):
            st.markdown(msg)

    prompt = st.chat_input("Type your question...")
    if prompt:
        st.session_state.chat_history.append(("user", prompt))
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                reply = generate_ai_reply(prompt)
                time.sleep(0.35)
            st.markdown(reply)

        st.session_state.chat_history.append(("assistant", reply))

        lead_id = st.session_state.get("current_lead_id")
        if isinstance(lead_id, int):
            increment_ai_replies_count(lead_id)
            # persist last reply as well
            set_automation_status(lead_id, status="completed", chatbot_reply=reply)


def render_admin_dashboard() -> None:
    st.subheader("Leads")
    df = list_leads()

    if df.empty:
        st.info("No leads submitted yet.")
        return

    col1, col2 = st.columns(2)
    with col1:
        status_filter = st.selectbox(
            "Automation Status",
            options=["all"] + sorted(df.get("automation_status", pd.Series([], dtype=str)).dropna().unique().tolist()),
            index=0,
        )
    with col2:
        dept_filter = st.text_input("Search Department / Interest")

    filtered = df.copy()
    if status_filter != "all" and "automation_status" in filtered.columns:
        filtered = filtered[filtered["automation_status"] == status_filter]
    if dept_filter.strip() and "department" in filtered.columns:
        filtered = filtered[filtered["department"].astype(str).str.contains(dept_filter.strip(), case=False, na=False)]

    st.write(f"Showing {len(filtered)} lead(s)")

    # Editable only: automation_status, priority
    disabled_cols = [c for c in filtered.columns if c not in {"automation_status", "priority"}]

    # st.data_editor expects disabled list; set per column
    column_config = {}
    for c in disabled_cols:
        column_config[c] = st.column_config.TextColumn(disabled=True)
    if "automation_status" in filtered.columns:
        column_config["automation_status"] = st.column_config.TextColumn(disabled=False)
    if "priority" in filtered.columns:
        column_config["priority"] = st.column_config.TextColumn(disabled=False)

    edited = st.data_editor(
        filtered,
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
        key="leads_editor",
    )

    # Apply updates back to DB if changed
    if isinstance(edited, pd.DataFrame) and not edited.empty:
        # Identify changed rows by id
        if "id" in edited.columns:
            original = filtered
            # This is simplistic; apply latest values for visible IDs
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            try:
                for _, row in edited.iterrows():
                    lead_id = int(row["id"])
                    new_status = str(row.get("automation_status", "pending"))
                    new_priority = str(row.get("priority", "Low"))
                    cur.execute(
                        "UPDATE leads SET automation_status = ?, priority = ? WHERE id = ?",
                        (new_status, new_priority, lead_id),
                    )
                conn.commit()
            finally:
                conn.close()


def render_settings() -> None:
    st.markdown(
        """
        <div class="bb-section">
          <h3 style="margin:0 0 8px 0;">Settings</h3>
          <div style="color:#cbd5e1; font-size:14px;">Coming soon</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.info("Coming soon")


# -----------------------------
# Router
# -----------------------------


def main() -> None:
    ensure_db()
    _inject_styles()

    _brand_top_nav()

    # Initialize active_tab if missing
    if "active_tab" not in st.session_state:
        st.session_state.active_tab = "Dashboard"

    # Render conditional sections
    if st.session_state.active_tab == "Dashboard":
        render_dashboard()
        st.divider()
        st.markdown(
            """
            <div class="bb-section" style="margin-top:12px;">
              <h3 style="margin:0 0 8px 0;">Admin Panel</h3>
              <div style="color:#cbd5e1; font-size:14px;">Edit automation status & priority</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        render_admin_dashboard()

    elif st.session_state.active_tab == "Leads":
        render_leads_form()
        st.divider()
        st.markdown(
            """
            <div class="bb-section" style="margin-top:12px;">
              <h3 style="margin:0 0 8px 0;">Admin Panel</h3>
              <div style="color:#cbd5e1; font-size:14px;">View and update leads</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        render_admin_dashboard()

    elif st.session_state.active_tab == "Chat":
        render_chatbot()
        # Optionally show lead context
        lead_id = st.session_state.get("current_lead_id")
        if isinstance(lead_id, int):
            st.caption(f"Current lead context: #{lead_id}")

    elif st.session_state.active_tab == "Settings":
        render_settings()


if __name__ == "__main__":
    main()


# Dependencies (for reproducibility)
# streamlit==1.38.0
# pandas==2.2.3
# sqlalchemy==2.0.32
# python-dateutil==2.9.0.post0
# plotly

