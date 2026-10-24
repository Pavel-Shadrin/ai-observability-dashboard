import json
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st


# ==================================================
# 1. PAGE CONFIGURATION
# ==================================================

st.set_page_config(
    page_title="AI Observability Dashboard",
    page_icon="📊",
    layout="wide",
)

BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "sample_logs.csv"
ALERT_FILE = BASE_DIR / "alert_history.csv"

ALERT_COLUMNS = [
    "timestamp",
    "event",
    "status",
    "reason",
    "error_rate",
    "avg_latency_ms",
    "signature",
]

st.title("📊 Mini AI Observability Dashboard")
st.caption(
    "Monitor AI request performance, investigate failures, "
    "detect anomalies, and track service health."
)


# ==================================================
# 2. LOAD REQUEST LOGS
# ==================================================

@st.cache_data
def load_data(file_path, file_modified):
    data = pd.read_csv(file_path)
    data.columns = data.columns.str.strip()

    required = {"request_id", "status", "latency_ms", "timestamp"}
    missing = required - set(data.columns)

    if missing:
        raise ValueError(
            "Missing required columns: " + ", ".join(sorted(missing))
        )

    data["request_id"] = data["request_id"].astype(str).str.strip()
    data["status"] = data["status"].astype(str).str.strip().str.lower()
    data["latency_ms"] = pd.to_numeric(
        data["latency_ms"], errors="coerce"
    )
    data["timestamp"] = pd.to_datetime(
        data["timestamp"], errors="coerce", utc=True
    )

    if "error_type" not in data.columns:
        data["error_type"] = "Unspecified"
    else:
        data["error_type"] = (
            data["error_type"]
            .fillna("Unspecified")
            .astype(str)
            .str.strip()
            .replace("", "Unspecified")
        )

    return data


if not LOG_FILE.exists():
    st.error(
        f"Cannot find {LOG_FILE.name}. "
        "Place it in the same folder as app.py."
    )
    st.stop()

try:
    df = load_data(str(LOG_FILE), LOG_FILE.stat().st_mtime)
except Exception as exc:
    st.error(f"Could not load request logs: {exc}")
    st.stop()

df = df.dropna(subset=["timestamp", "latency_ms"]).copy()

if df.empty:
    st.warning("No valid request records were found in sample_logs.csv.")
    st.stop()


# ==================================================
# 3. SIDEBAR SETTINGS
# ==================================================

st.sidebar.title("⚙️ Dashboard Settings")

st.sidebar.caption("These settings update the dashboard calculations.")

latency_threshold = st.sidebar.slider(
    "Slow request threshold (ms)",
    min_value=100,
    max_value=5000,
    value=1000,
    step=100,
)

time_window = st.sidebar.selectbox(
    "Time window",
    [
        "All available data",
        "Last 15 minutes",
        "Last 1 hour",
        "Last 6 hours",
        "Last 24 hours",
    ],
)

anomaly_multiplier = st.sidebar.select_slider(
    "Anomaly sensitivity",
    options=[1.0, 1.5, 2.0, 2.5, 3.0],
    value=1.5,
)

st.sidebar.divider()
st.sidebar.subheader("Service Health Thresholds")

warning_error_rate = st.sidebar.slider(
    "Warning error rate (%)",
    min_value=1,
    max_value=50,
    value=10,
    step=1,
)

critical_error_rate = st.sidebar.slider(
    "Critical error rate (%)",
    min_value=warning_error_rate + 1,
    max_value=100,
    value=max(25, warning_error_rate + 1),
    step=1,
)

warning_latency = st.sidebar.slider(
    "Warning average latency (ms)",
    min_value=100,
    max_value=5000,
    value=1000,
    step=100,
)

critical_latency = st.sidebar.slider(
    "Critical average latency (ms)",
    min_value=warning_latency + 100,
    max_value=10000,
    value=max(2000, warning_latency + 100),
    step=100,
)

st.sidebar.divider()
st.sidebar.caption(f"Source file: {LOG_FILE.name}")
st.sidebar.caption(f"Records loaded: {len(df):,}")


# ==================================================
# 4. TIME-WINDOW FILTER
# ==================================================

newest_timestamp = df["timestamp"].max()

window_minutes = {
    "Last 15 minutes": 15,
    "Last 1 hour": 60,
    "Last 6 hours": 360,
    "Last 24 hours": 1440,
}

if time_window == "All available data":
    filtered_df = df.copy()
else:
    cutoff = newest_timestamp - pd.Timedelta(
        minutes=window_minutes[time_window]
    )
    filtered_df = df[df["timestamp"] >= cutoff].copy()

if filtered_df.empty:
    st.warning(
        "No requests fall within this time window. "
        "Choose a wider window in the sidebar."
    )
    st.stop()


# ==================================================
# 5. REQUEST CLASSIFICATION AND METRICS
# ==================================================

success_statuses = {"success", "successful", "ok", "200"}
error_statuses = {
    "error", "errors", "failed", "failure", "fail",
    "500", "502", "503", "504",
}

filtered_df["is_success"] = filtered_df["status"].isin(
    success_statuses
)
filtered_df["is_error"] = filtered_df["status"].isin(
    error_statuses
)
filtered_df["is_slow"] = (
    filtered_df["latency_ms"] > latency_threshold
)

total_requests = len(filtered_df)
successful_requests = int(filtered_df["is_success"].sum())
failed_requests = int(filtered_df["is_error"].sum())

error_rate = (
    failed_requests / total_requests * 100 if total_requests else 0
)
success_rate = (
    successful_requests / total_requests * 100 if total_requests else 0
)

average_latency = float(filtered_df["latency_ms"].mean())
median_latency = float(filtered_df["latency_ms"].median())
p50_latency = float(filtered_df["latency_ms"].quantile(0.50))
p95_latency = float(filtered_df["latency_ms"].quantile(0.95))
p99_latency = float(filtered_df["latency_ms"].quantile(0.99))

slow_requests = int(filtered_df["is_slow"].sum())
slow_request_rate = (
    slow_requests / total_requests * 100 if total_requests else 0
)


# ==================================================
# 6. ANOMALY DETECTION
# ==================================================

q1 = filtered_df["latency_ms"].quantile(0.25)
q3 = filtered_df["latency_ms"].quantile(0.75)
iqr = q3 - q1

anomaly_threshold = q3 + anomaly_multiplier * iqr

anomalies_df = filtered_df[
    filtered_df["latency_ms"] > anomaly_threshold
].copy()

anomaly_count = len(anomalies_df)


# ==================================================
# 7. SERVICE HEALTH ASSESSMENT
# ==================================================

critical_reasons = []
warning_reasons = []

if error_rate >= critical_error_rate:
    critical_reasons.append(
        f"Error rate is {error_rate:.1f}%, reaching the critical "
        f"threshold of {critical_error_rate}%."
    )
elif error_rate >= warning_error_rate:
    warning_reasons.append(
        f"Error rate is {error_rate:.1f}%, reaching the warning "
        f"threshold of {warning_error_rate}%."
    )

if average_latency >= critical_latency:
    critical_reasons.append(
        f"Average latency is {average_latency:.0f} ms, reaching the "
        f"critical threshold of {critical_latency} ms."
    )
elif average_latency >= warning_latency:
    warning_reasons.append(
        f"Average latency is {average_latency:.0f} ms, reaching the "
        f"warning threshold of {warning_latency} ms."
    )

if critical_reasons:
    health_status = "Unhealthy"
    health_reasons = critical_reasons + warning_reasons
elif warning_reasons:
    health_status = "Degraded"
    health_reasons = warning_reasons
else:
    health_status = "Healthy"
    health_reasons = ["No configured health thresholds were breached."]

current_signature = json.dumps(
    {"status": health_status, "reasons": health_reasons},
    sort_keys=True,
)


# ==================================================
# 8. PERSISTENT ALERT HISTORY
# ==================================================

def load_alert_history():
    if not ALERT_FILE.exists():
        return pd.DataFrame(columns=ALERT_COLUMNS)

    try:
        history = pd.read_csv(ALERT_FILE)

        for column in ALERT_COLUMNS:
            if column not in history.columns:
                history[column] = ""

        return history[ALERT_COLUMNS].fillna("")

    except (OSError, pd.errors.ParserError, UnicodeDecodeError):
        st.warning(
            "The saved alert history could not be read. "
            "The existing file has not been deleted."
        )
        return pd.DataFrame(columns=ALERT_COLUMNS)


def save_alert_history(history):
    history[ALERT_COLUMNS].to_csv(ALERT_FILE, index=False)


def add_alert(history, event, status, reason, signature):
    record = {
        "timestamp": pd.Timestamp.now(tz="UTC").isoformat(),
        "event": event,
        "status": status,
        "reason": reason,
        "error_rate": round(error_rate, 2),
        "avg_latency_ms": round(average_latency, 2),
        "signature": signature,
    }

    updated = pd.concat(
        [history, pd.DataFrame([record])],
        ignore_index=True,
    )
    save_alert_history(updated)
    return updated


if "alert_history" not in st.session_state:
    st.session_state.alert_history = load_alert_history()

if "last_health_signature" not in st.session_state:
    saved = st.session_state.alert_history

    if not saved.empty:
        latest = saved.iloc[-1]
        saved_signature = str(latest["signature"])

        st.session_state.last_health_signature = (
            saved_signature if saved_signature else None
        )
        st.session_state.last_health_status = str(latest["status"])
    else:
        st.session_state.last_health_signature = None
        st.session_state.last_health_status = "Healthy"

previous_signature = st.session_state.last_health_signature
previous_status = st.session_state.last_health_status

if health_status in {"Degraded", "Unhealthy"}:
    if current_signature != previous_signature:
        event_name = (
            "Critical" if health_status == "Unhealthy" else "Warning"
        )

        st.session_state.alert_history = add_alert(
            st.session_state.alert_history,
            event_name,
            health_status,
            " ".join(health_reasons),
            current_signature,
        )

        st.session_state.last_health_signature = current_signature
        st.session_state.last_health_status = health_status

elif health_status == "Healthy":
    if previous_status in {"Degraded", "Unhealthy"}:
        st.session_state.alert_history = add_alert(
            st.session_state.alert_history,
            "Resolved",
            "Healthy",
            f"Service returned to Healthy. Previous status: {previous_status}.",
            current_signature,
        )

    st.session_state.last_health_signature = current_signature
    st.session_state.last_health_status = "Healthy"


# ==================================================
# 9. PREPARE DATA FOR CHARTS AND EXPORTS
# ==================================================

errors_df = filtered_df[filtered_df["is_error"]].copy()

slow_df = filtered_df[
    filtered_df["latency_ms"] > latency_threshold
].copy()

history = st.session_state.alert_history.copy()

percentile_chart = pd.DataFrame(
    {
        "Percentile": ["p50", "p95", "p99"],
        "Latency (ms)": [p50_latency, p95_latency, p99_latency],
    }
).set_index("Percentile")

errors_by_category = (
    errors_df.groupby("error_type")
    .size()
    .sort_values(ascending=False)
    .rename("Failed requests")
)

latency_over_time = (
    filtered_df.set_index("timestamp")["latency_ms"].sort_index()
)

latency_values = filtered_df["latency_ms"].dropna().to_numpy()

if len(latency_values) > 0:
    bin_count = min(20, max(5, int(np.sqrt(len(latency_values)))))
    histogram_counts, bin_edges = np.histogram(
        latency_values, bins=bin_count
    )

    histogram_df = pd.DataFrame(
        {
            "Latency range (ms)": [
                f"{bin_edges[i]:.0f}–{bin_edges[i + 1]:.0f}"
                for i in range(len(histogram_counts))
            ],
            "Request count": histogram_counts,
        }
    ).set_index("Latency range (ms)")


# ==================================================
# 10. GLOBAL SUMMARY AND HEALTH INDICATOR
# ==================================================

st.caption(
    f"Time window: {time_window} · "
    f"{total_requests:,} requests · "
    f"Newest log: {newest_timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}"
)

if health_status == "Healthy":
    st.success("● SERVICE HEALTH: HEALTHY")
elif health_status == "Degraded":
    st.warning("● SERVICE HEALTH: DEGRADED — review warning conditions")
else:
    st.error("● SERVICE HEALTH: UNHEALTHY — critical conditions detected")

summary1, summary2, summary3, summary4 = st.columns(4)

summary1.metric("Requests", f"{total_requests:,}")
summary2.metric("Error rate", f"{error_rate:.2f}%")
summary3.metric("Average latency", f"{average_latency:.0f} ms")
summary4.metric("Anomalies", f"{anomaly_count:,}")


# ==================================================
# 11. FOUR DASHBOARD TABS
# ==================================================

overview_tab, performance_tab, alerts_tab, investigation_tab = st.tabs(
    [
        "🏠 Overview",
        "📈 Performance",
        "🚨 Alerts",
        "🔎 Request Investigation",
    ]
)


# ==================================================
# TAB 1: OVERVIEW
# ==================================================

with overview_tab:
    st.header("Overview")
    st.write(
        "A high-level view of request volume, reliability, and service health."
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Successful requests", f"{successful_requests:,}")
    col2.metric("Failed requests", f"{failed_requests:,}")
    col3.metric("Success rate", f"{success_rate:.2f}%")
    col4.metric("Slow requests", f"{slow_requests:,}")

    st.subheader("Service Health Assessment")

    for reason in health_reasons:
        st.write(f"- {reason}")

    st.subheader("Current Metrics vs. Health Thresholds")

    health_checks = pd.DataFrame(
        [
            {
                "Metric": "Error rate",
                "Current value": f"{error_rate:.2f}%",
                "Warning threshold": f"{warning_error_rate}%",
                "Critical threshold": f"{critical_error_rate}%",
                "Result": (
                    "Critical"
                    if error_rate >= critical_error_rate
                    else "Warning"
                    if error_rate >= warning_error_rate
                    else "Within thresholds"
                ),
            },
            {
                "Metric": "Average latency",
                "Current value": f"{average_latency:.0f} ms",
                "Warning threshold": f"{warning_latency} ms",
                "Critical threshold": f"{critical_latency} ms",
                "Result": (
                    "Critical"
                    if average_latency >= critical_latency
                    else "Warning"
                    if average_latency >= warning_latency
                    else "Within thresholds"
                ),
            },
        ]
    )

    st.dataframe(
        health_checks,
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        "Healthy means both metrics are below their warning thresholds. "
        "Failed requests remain visible in the metrics and investigation tools, "
        "but do not independently change the health status."
    )

    with st.expander("How service health is calculated"):
        st.write(
            "**Unhealthy:** a critical error-rate or average-latency "
            "threshold has been reached."
        )
        st.write(
            "**Degraded:** the error rate or average latency has reached "
            "its warning threshold but has not reached a critical threshold."
        )
        st.write(
            "**Healthy:** none of the configured warning or critical "
            "conditions has been triggered."
        )

    st.subheader("Latency Percentiles")

    pcol1, pcol2, pcol3 = st.columns(3)
    pcol1.metric("p50 latency", f"{p50_latency:.0f} ms")
    pcol2.metric("p95 latency", f"{p95_latency:.0f} ms")
    pcol3.metric("p99 latency", f"{p99_latency:.0f} ms")

    st.bar_chart(percentile_chart)

    st.caption(
        "p50 is the median. p95 and p99 show the latency below which "
        "95% and 99% of requests completed, respectively."
    )


# ==================================================
# TAB 2: PERFORMANCE
# ==================================================

with performance_tab:
    st.header("Performance Analysis")

    st.subheader("Latency Over Time")
    st.line_chart(latency_over_time, y_label="Latency (ms)")

    st.subheader("Latency Distribution")

    if len(latency_values) == 0:
        st.info("No valid latency values are available.")
    else:
        st.bar_chart(histogram_df)

    st.subheader("Errors by Category")

    if errors_df.empty:
        st.info("No failed requests in the selected time window.")
    else:
        st.bar_chart(errors_by_category)

    st.subheader("Slow Requests")

    slow_col1, slow_col2 = st.columns(2)
    slow_col1.metric("Slow requests", f"{slow_requests:,}")
    slow_col2.metric("Slow request rate", f"{slow_request_rate:.2f}%")

    st.caption(
        f"A slow request is one with latency above {latency_threshold} ms."
    )

    if slow_df.empty:
        st.success("No requests exceeded the slow-request threshold.")
    else:
        st.dataframe(
            slow_df.sort_values("latency_ms", ascending=False),
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("Latency Anomaly Detection")

    anomaly_col1, anomaly_col2 = st.columns(2)
    anomaly_col1.metric("Detected anomalies", f"{anomaly_count:,}")
    anomaly_col2.metric("Anomaly threshold", f"{anomaly_threshold:.0f} ms")

    st.caption(
        "Uses the interquartile range (IQR): Q3 + sensitivity × IQR. "
        "An anomaly is a statistical outlier, not necessarily a failure."
    )

    if anomalies_df.empty:
        st.success("No latency anomalies were detected.")
    else:
        st.dataframe(
            anomalies_df.sort_values("latency_ms", ascending=False),
            use_container_width=True,
            hide_index=True,
        )


# ==================================================
# TAB 3: ALERTS
# ==================================================

with alerts_tab:
    st.header("Alert Centre")

    st.caption(
        "Alert events are saved in alert_history.csv and can persist "
        "between app sessions."
    )

    alert_col1, alert_col2, alert_col3 = st.columns(3)

    alert_col1.metric("Recorded events", f"{len(history):,}")

    alert_col2.metric(
        "Warning events",
        int((history["event"] == "Warning").sum())
        if not history.empty else 0,
    )

    alert_col3.metric(
        "Critical events",
        int((history["event"] == "Critical").sum())
        if not history.empty else 0,
    )

    if history.empty:
        st.info(
            "No alerts have been recorded yet. "
            "An alert is recorded when the service health state changes."
        )
    else:
        display_history = history.copy()

        display_history["timestamp"] = pd.to_datetime(
            display_history["timestamp"],
            errors="coerce",
            utc=True,
        )

        display_history = display_history.sort_values(
            "timestamp",
            ascending=False,
            na_position="last",
        )

        st.dataframe(
            display_history[
                [
                    "timestamp",
                    "event",
                    "status",
                    "reason",
                    "error_rate",
                    "avg_latency_ms",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

    with st.expander("Saved alert file location"):
        st.code(str(ALERT_FILE))

    # Incident report download
    report_lines = [
        "MINI AI OBSERVABILITY DASHBOARD",
        "INCIDENT AND SERVICE HEALTH REPORT",
        "=" * 42,
        "",
        f"Generated (UTC): {pd.Timestamp.now(tz='UTC').isoformat()}",
        f"Time window: {time_window}",
        "",
        "SERVICE HEALTH",
        "-" * 20,
        f"Status: {health_status}",
        f"Reasons: {' '.join(health_reasons)}",
        "",
        "REQUEST METRICS",
        "-" * 20,
        f"Total requests: {total_requests}",
        f"Successful requests: {successful_requests}",
        f"Failed requests: {failed_requests}",
        f"Success rate: {success_rate:.2f}%",
        f"Error rate: {error_rate:.2f}%",
        "",
        "LATENCY METRICS",
        "-" * 20,
        f"Average latency: {average_latency:.2f} ms",
        f"Median latency: {median_latency:.2f} ms",
        f"p50 latency: {p50_latency:.2f} ms",
        f"p95 latency: {p95_latency:.2f} ms",
        f"p99 latency: {p99_latency:.2f} ms",
        f"Slow request threshold: {latency_threshold} ms",
        f"Slow requests: {slow_requests}",
        "",
        "ANOMALY DETECTION",
        "-" * 20,
        "Method: IQR",
        f"Sensitivity multiplier: {anomaly_multiplier}",
        f"Anomaly threshold: {anomaly_threshold:.2f} ms",
        f"Detected anomalies: {anomaly_count}",
        "",
        "RECENT ALERT EVENTS",
        "-" * 20,
    ]

    if history.empty:
        report_lines.append("No alert events recorded.")
    else:
        for _, alert in history.tail(10).iloc[::-1].iterrows():
            report_lines.extend(
                [
                    f"Time: {alert['timestamp']}",
                    f"Event: {alert['event']}",
                    f"Status: {alert['status']}",
                    f"Reason: {alert['reason']}",
                    "-" * 20,
                ]
            )

    report_lines.extend(
        [
            "",
            "This report summarizes the selected request logs.",
            "It does not represent continuous production monitoring.",
        ]
    )

    st.download_button(
        "📄 Download incident report (TXT)",
        data="\n".join(report_lines),
        file_name="incident_report.txt",
        mime="text/plain",
        key="download_incident_report",
    )

    st.divider()

    st.subheader("Manage Alert History")

    st.warning(
        "Clearing history permanently empties the local alert_history.csv file."
    )

    if st.button("Clear alert history", key="clear_alert_history"):
        try:
            empty_history = pd.DataFrame(columns=ALERT_COLUMNS)
            save_alert_history(empty_history)

            st.session_state.alert_history = empty_history
            st.session_state.last_health_signature = current_signature
            st.session_state.last_health_status = health_status

            st.success("Alert history cleared.")
            st.rerun()

        except OSError as exc:
            st.error(f"Could not clear alert history: {exc}")


# ==================================================
# TAB 4: REQUEST INVESTIGATION
# ==================================================

with investigation_tab:
    st.header("Request Investigation")

    st.subheader("Request Log Explorer")

    selected_status = st.selectbox(
        "Filter logs by status",
        ["All", "Success", "Errors"],
        key="request_status_filter",
    )

    if selected_status == "Success":
        request_view = filtered_df[filtered_df["is_success"]].copy()
    elif selected_status == "Errors":
        request_view = filtered_df[filtered_df["is_error"]].copy()
    else:
        request_view = filtered_df.copy()

    st.dataframe(
        request_view.sort_values("timestamp", ascending=False),
        use_container_width=True,
        hide_index=True,
    )

    export_df = request_view.drop(
        columns=["is_success", "is_error", "is_slow"],
        errors="ignore",
    ).copy()

    export_df["timestamp"] = export_df["timestamp"].astype(str)

    csv_buffer = StringIO()
    export_df.to_csv(csv_buffer, index=False)

    st.download_button(
        "⬇️ Download filtered request logs (CSV)",
        data=csv_buffer.getvalue(),
        file_name="filtered_request_logs.csv",
        mime="text/csv",
        key="download_filtered_logs",
    )

    st.caption(
        f"The CSV contains {len(export_df):,} request(s) matching "
        "the selected time window and status filter."
    )

    st.divider()
    st.subheader("Failed Request Investigation")

    if errors_df.empty:
        st.info("No failed requests were found in this time window.")
    else:
        available_error_types = sorted(
            errors_df["error_type"].dropna().astype(str).unique().tolist()
        )

        selected_error_type = st.selectbox(
            "Filter failed requests by category",
            ["All categories"] + available_error_types,
            key="investigation_error_category",
        )

        investigation_df = errors_df.copy()

        if selected_error_type != "All categories":
            investigation_df = investigation_df[
                investigation_df["error_type"].astype(str)
                == selected_error_type
            ]

        if investigation_df.empty:
            st.info("No failed requests match this category.")
        else:
            investigation_df = investigation_df.sort_values(
                "timestamp",
                ascending=False,
            )

            investigation_df["request_label"] = (
                investigation_df["request_id"].astype(str)
                + " | "
                + investigation_df["error_type"].astype(str)
                + " | "
                + investigation_df["latency_ms"].round(0).astype(str)
                + " ms"
            )

            selected_label = st.selectbox(
                "Choose a failed request",
                investigation_df["request_label"].tolist(),
                key="failed_request_selector",
            )

            selected_request = investigation_df[
                investigation_df["request_label"] == selected_label
            ].iloc[0]

            st.markdown(
                f"**Request ID:** `{selected_request['request_id']}`"
            )

            detail_col1, detail_col2, detail_col3 = st.columns(3)

            detail_col1.metric(
                "Latency",
                f"{selected_request['latency_ms']:.0f} ms",
            )

            detail_col2.metric(
                "Error category",
                str(selected_request["error_type"]),
            )

            detail_col3.metric(
                "Status",
                str(selected_request["status"]),
            )

            with st.expander("View all request fields", expanded=True):
                st.json(
                    {
                        str(key): (
                            value.isoformat()
                            if isinstance(value, pd.Timestamp)
                            else str(value)
                        )
                        for key, value in selected_request.drop(
                            labels=["request_label"],
                            errors="ignore",
                        ).items()
                    }
                )

    st.divider()
    st.subheader("Complete Filtered Dataset")

    with st.expander("Show all records in the selected time window"):
        st.dataframe(
            filtered_df.sort_values("timestamp", ascending=False),
            use_container_width=True,
            hide_index=True,
        )


# ==================================================
# 12. FOOTER
# ==================================================

st.divider()

st.caption(
    "Mini AI Observability Dashboard · Local prototype using mock request logs"
)