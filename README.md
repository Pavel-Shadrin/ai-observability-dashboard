
# Mini AI Observability Dashboard

A Python-based dashboard for monitoring and investigating AI-style service request logs. It helps users understand request performance, identify failures, detect unusual latency, and review service health through an interactive interface.

## Overview

The Mini AI Observability Dashboard is a portfolio project inspired by observability tools used to monitor software systems and AI applications.

It processes a dataset of mock request logs and presents useful metrics, charts, alerts, and investigation tools in one place.

**Note:** This version uses sample data. It is a local prototype, not a live production monitoring system.

## Features

- **Request monitoring:** View total requests, successful requests, failed requests, and error rates.
- **Time filtering:** Focus on selected time windows.
- **Performance analysis:** Examine request latency using charts, averages, medians, and percentiles.
- **Slow request detection:** Set a latency threshold to identify slow requests.
- **Anomaly detection:** Use interquartile range (IQR) analysis to flag unusual latency values.
- **Service health indicators:** Review warning and critical conditions based on configured thresholds.
- **Alert history:** Record and review alert events locally.
- **Failure investigation:** Examine failed requests and their error categories.
- **Data exports:** Download filtered logs as CSV and incident reports as text.

## Technology Stack

- Python
- Streamlit
- Pandas
- NumPy
- CSV for sample data and local alert history

## Project Structure

```text
mini-ai-observability-dashboard/
├── app.py
├── sample_logs.csv
├── README.md
├── alert_history.csv     # Created when alert history is recorded
└── screenshots/
    └── dashboard-overview.png
```

The `screenshots/` folder and `alert_history.csv` may not exist until you create the screenshot folder or the application records alerts.

## Getting Started

### Requirements

- Python 3
- pip
- The project files listed above

### 1. Open a terminal

Navigate to the folder containing `app.py` and `sample_logs.csv`.

### 2. Install the dependencies

```bash
python3 -m pip install streamlit pandas numpy
```

### 3. Run the dashboard

```bash
python3 -m streamlit run app.py
```

Streamlit will provide a local URL to open the dashboard in your browser.

Keep `sample_logs.csv` in the same folder as `app.py`.

## How It Works

1. The application loads request logs from a CSV file.
2. Pandas processes the records, including timestamps, status values, and latency measurements.
3. The application calculates performance metrics and identifies potential issues.
4. Streamlit displays the results through interactive metrics, charts, filters, and investigation views.
5. Alert events can be stored locally in `alert_history.csv`.

## Screenshot

Add a screenshot of the dashboard here after creating the `screenshots/` folder.

Suggested file: `screenshots/dashboard-overview.png`

A screenshot will help visitors understand the interface without installing or running the project.

## Current Limitations

- Uses mock request logs rather than live AI service traffic.
- Reads local CSV data instead of a production database or logging platform.
- Does not connect directly to an AI model API.
- Does not perform continuous background monitoring.
- Alert evaluation occurs when the Streamlit application reruns, rather than through a separate monitoring service.
- Local alert history is not a shared or remotely hosted database.

## Future Improvements

- Integrate logs from a real AI API.
- Add token usage, model latency, and API cost tracking.
- Store logs in a database.
- Implement continuous monitoring and notification delivery.
- Add automated tests and a continuous integration workflow.
- Deploy the dashboard so other users can access it online.

## Purpose

This project explores the fundamentals of observability, performance monitoring, anomaly detection, and incident investigation using Python.

It is designed as a learning and portfolio project that can be expanded as new monitoring requirements are introduced.
