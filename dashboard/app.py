import os
import sys
import json
import streamlit as st
import pandas as pd
import sqlite3

# Add scripts directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "scripts"))

workspace_root = os.environ.get("WORKSPACE_ROOT", os.path.expanduser("~/opt-workspace"))

st.set_page_config(page_title="DecisionAI Intake Dashboard", layout="wide")

st.title("DecisionAI Optimization Pipeline")

pages = ["Overview", "Tenant Detail", "Job Monitor", "Cost Analysis", "System Health"]
page = st.sidebar.radio("Navigation", pages)

def get_db_connection():
    db_path = os.path.join(workspace_root, 'cost_tracker.db')
    if not os.path.exists(db_path):
        return None
    # Read-only URI mode to prevent lock issues in concurrent access
    uri = f"file:{db_path}?mode=ro"
    return sqlite3.connect(uri, uri=True)

if page == "Overview":
    st.header("System Overview")
    
    registry = os.path.join(workspace_root, 'tenants.json')
    if os.path.exists(registry):
        with open(registry, 'r') as f:
            tenants = json.load(f).get("tenants", [])
        st.metric("Active Tenants", len([t for t in tenants if t.get('active')]))
    else:
        st.warning("No tenants.json found.")
        
    conn = get_db_connection()
    if conn:
        df = pd.read_sql("SELECT status, count(*) as count FROM cost_records GROUP BY status", conn)
        st.subheader("Job Status Summary")
        st.dataframe(df)
        conn.close()
        
elif page == "Job Monitor":
    st.header("Live Job Monitor")
    conn = get_db_connection()
    if conn:
        df = pd.read_sql("SELECT tenant_id, request_id, job_id, billed_minutes, submitted_at, status, objective FROM cost_records ORDER BY submitted_at DESC LIMIT 50", conn)
        st.dataframe(df)
        conn.close()
    else:
        st.info("No cost tracking data available.")

elif page == "Cost Analysis":
    st.header("Cost Analysis")
    conn = get_db_connection()
    if conn:
        df = pd.read_sql("SELECT tenant_id, SUM(billed_minutes) as total_minutes FROM cost_records GROUP BY tenant_id", conn)
        st.bar_chart(df.set_index("tenant_id"))
        conn.close()

elif page == "System Health":
    st.header("System Health")
    from health_check import check_health
    # Fast check without alerting
    health = check_health(alert_slack=False)
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Gemini Flash", "UP" if health.gemini_flash.available else "DOWN")
    col2.metric("Gemini Pro", "UP" if health.gemini_pro.available else "DOWN")
    col3.metric("HybridSolver", "UP" if health.hybridsolver.available else "DOWN")
    col4.metric("Slack", "UP" if health.slack.available else "DOWN")
    
    st.metric("Disk Usage", f"{health.disk_usage_percent:.1f}%")
