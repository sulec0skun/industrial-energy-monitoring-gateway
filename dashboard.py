"""Local dashboard for the Industrial Energy Monitoring Gateway.

Telemetry is read exclusively from PostgreSQL. The source measurement timestamp
and the local database arrival timestamp are intentionally shown separately.
"""

import os
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import psycopg
from psycopg.rows import dict_row
import streamlit as st
from dotenv import load_dotenv


load_dotenv(Path(__file__).with_name(".env"))

LOCAL_TIMEZONE = ZoneInfo("Asia/Shanghai")
REFRESH_SECONDS = 5
MAX_CHART_ROWS = 10_000
MAX_INTEGRATION_GAP_SECONDS = 300
WINDOWS = {
    "Last 6 hours": 6,
    "Last 24 hours": 24,
    "Last 7 days": 168,
}

st.set_page_config(
    page_title="Industrial Energy Monitoring Gateway",
    page_icon="⚡",
    layout="wide",
)


def db_settings():
    # Bağlantı şifresini kodun içine yazmadan .env üzerinden oku.
    return {
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "dbname": os.getenv("DB_NAME", "energy_monitoring"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", ""),
        "connect_timeout": 5,
    }


def select_rows(query, parameters=()):
    # Her yenilemede bağlantıyı aç, sorgula ve güvenle kapat.
    with psycopg.connect(**db_settings(), row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, parameters)
            return cursor.fetchall()


def get_devices():
    rows = select_rows("SELECT DISTINCT device_id FROM telemetry ORDER BY device_id")
    return [row["device_id"] for row in rows]


def get_latest(device_id):
    rows = select_rows(
        """
        SELECT device_id, measurement_timestamp, received_timestamp,
               voltage, current, power, temperature
        FROM telemetry
        WHERE device_id = %s
        ORDER BY id DESC
        LIMIT 1
        """,
        (device_id,),
    )
    return rows[0] if rows else None


def get_history(device_id, hours):
    # Son veri seti saatine göre geriye git; geçmiş simülasyon verileri de çalışsın.
    rows = select_rows(
        """
        SELECT measurement_timestamp, received_timestamp,
               voltage, current, power, temperature
        FROM telemetry
        WHERE device_id = %s
          AND measurement_timestamp >= (
              SELECT MAX(measurement_timestamp) - (%s * INTERVAL '1 hour')
              FROM telemetry WHERE device_id = %s
          )
        ORDER BY measurement_timestamp DESC
        LIMIT %s
        """,
        (device_id, hours, device_id, MAX_CHART_ROWS),
    )
    dataframe = pd.DataFrame(rows)
    if dataframe.empty:
        return dataframe

    dataframe["measurement_timestamp"] = pd.to_datetime(
        dataframe["measurement_timestamp"], utc=True
    )
    dataframe["received_timestamp"] = pd.to_datetime(
        dataframe["received_timestamp"], utc=True
    )
    dataframe = dataframe.sort_values("measurement_timestamp").reset_index(drop=True)
    dataframe["local_time"] = (
        dataframe["measurement_timestamp"]
        .dt.tz_convert(LOCAL_TIMEZONE)
        .dt.tz_localize(None)
    )
    return dataframe


def estimate_daily_energy(dataframe):
    # Komşu güç ölçümlerini trapez yöntemiyle yaklaşık kWh'ye dönüştür.
    # Uzun veri boşluklarını ve gün sınırını aşan aralıkları hesaba katma.
    calculations = dataframe[["measurement_timestamp", "power", "local_time"]].copy()
    calculations["local_date"] = calculations["local_time"].dt.date
    calculations["previous_timestamp"] = calculations["measurement_timestamp"].shift(1)
    calculations["previous_power"] = calculations["power"].shift(1)
    calculations["previous_date"] = calculations["local_date"].shift(1)
    seconds = (
        calculations["measurement_timestamp"]
        - calculations["previous_timestamp"]
    ).dt.total_seconds()
    valid = (
        seconds.gt(0)
        & seconds.le(MAX_INTEGRATION_GAP_SECONDS)
        & calculations["local_date"].eq(calculations["previous_date"])
    )
    calculations["energy_kwh"] = 0.0
    calculations.loc[valid, "energy_kwh"] = (
        (calculations.loc[valid, "previous_power"] + calculations.loc[valid, "power"])
        / 2
        * seconds.loc[valid]
        / 3_600_000
    )
    result = (
        calculations.groupby("local_date", as_index=False)["energy_kwh"]
        .sum()
        .rename(columns={"local_date": "Date", "energy_kwh": "Estimated energy (kWh)"})
    )
    result["Date"] = result["Date"].astype(str)
    return result


def format_time(value, local=True):
    target = LOCAL_TIMEZONE if local else timezone.utc
    return value.astimezone(target).strftime("%Y-%m-%d %H:%M:%S %Z")


st.title("⚡ Industrial Energy Monitoring Gateway")
st.caption(
    "Local industrial IoT monitoring • Modbus TCP → MQTT → PostgreSQL • "
    "Real measurements replayed from a historical energy dataset"
)

try:
    devices = get_devices()
except (psycopg.Error, ValueError) as exc:
    st.error(f"Database connection unavailable ({type(exc).__name__}). Start PostgreSQL and check .env.")
    st.stop()

if not devices:
    st.info("No telemetry is stored yet. Start the simulator, MQTT subscriber, and gateway.")
    st.stop()

st.sidebar.header("Monitoring settings")
device_id = st.sidebar.selectbox("Device", devices)
window_label = st.sidebar.selectbox("Measurement time window", list(WINDOWS), index=2)
temperature_limit = st.sidebar.number_input(
    "Temperature alert threshold (°C)", min_value=0.0, value=45.0, step=1.0
)
power_limit = st.sidebar.number_input(
    "Power alert threshold (W)", min_value=0.0, value=2000.0, step=100.0
)
st.sidebar.caption("Alert thresholds are illustrative demo settings, not manufacturer limits.")
st.sidebar.caption(f"Auto-refresh: every {REFRESH_SECONDS} seconds")


@st.fragment(run_every=f"{REFRESH_SECONDS}s")
def render_dashboard(selected_device, window_hours, temp_threshold, power_threshold):
    try:
        latest = get_latest(selected_device)
        history = get_history(selected_device, window_hours)
    except (psycopg.Error, ValueError) as exc:
        st.error(f"Telemetry query failed ({type(exc).__name__}). Check PostgreSQL.")
        return

    if latest is None or history.empty:
        st.info("No telemetry available for this device and time window.")
        return

    st.subheader("Latest received measurement")
    metrics = st.columns(4)
    metrics[0].metric("Voltage", f"{latest['voltage']:.2f} V")
    metrics[1].metric("Current", f"{latest['current']:.2f} A")
    metrics[2].metric("PV power", f"{latest['power']:.2f} W")
    metrics[3].metric("Temperature", f"{latest['temperature']:.2f} °C")

    st.caption(
        f"Source measurement: {format_time(latest['measurement_timestamp'])} "
        f"(Asia/Shanghai)  |  "
        f"Stored at: {format_time(latest['received_timestamp'], local=False)} (UTC)"
    )

    st.subheader("Operational alerts")
    alerts = []
    if latest["temperature"] >= temp_threshold:
        alerts.append(f"Temperature reached {latest['temperature']:.1f} °C (demo threshold: {temp_threshold:.1f} °C).")
    if latest["power"] >= power_threshold:
        alerts.append(f"Power reached {latest['power']:.1f} W (demo threshold: {power_threshold:.1f} W).")

    seconds_since_receive = (
        datetime.now(timezone.utc) - latest["received_timestamp"].astimezone(timezone.utc)
    ).total_seconds()
    if seconds_since_receive > 90:
        st.info(
            "No new telemetry has been stored in the last 90 seconds. "
            "The replay may be completed or the gateway may be paused."
        )
    if alerts:
        for alert in alerts:
            st.warning(alert)
    else:
        st.success("No threshold-based alerts for the latest measurement.")

    st.subheader("Historical telemetry")
    st.caption("Chart time axis: source measurement time in Asia/Shanghai, not the replay time.")
    left, right = st.columns(2)
    with left:
        st.markdown("**PV power (W)**")
        st.line_chart(history, x="local_time", y="power", x_label="Measurement time", y_label="W")
        st.markdown("**Voltage (V)**")
        st.line_chart(history, x="local_time", y="voltage", x_label="Measurement time", y_label="V")
    with right:
        st.markdown("**Temperature (°C)**")
        st.line_chart(history, x="local_time", y="temperature", x_label="Measurement time", y_label="°C")
        st.markdown("**Current (A)**")
        st.line_chart(history, x="local_time", y="current", x_label="Measurement time", y_label="A")

    st.subheader("Energy analytics")
    daily_energy = estimate_daily_energy(history)
    total_energy = daily_energy["Estimated energy (kWh)"].sum()
    summary_left, summary_right = st.columns([1, 3])
    with summary_left:
        st.metric("Estimated energy in selected window", f"{total_energy:.3f} kWh")
        st.metric("Peak power in selected window", f"{history['power'].max():.1f} W")
    with summary_right:
        st.bar_chart(daily_energy, x="Date", y="Estimated energy (kWh)", x_label="Shenzhen date")
    st.caption(
        "Energy is estimated from successive PV power samples (trapezoidal method). "
        "Gaps over 5 minutes are excluded; incomplete periods may underestimate production. "
        "Only the selected historical window is included."
    )

    with st.expander("Recent stored measurements"):
        visible = history.tail(20).sort_values("local_time", ascending=False)
        st.dataframe(
            visible[["local_time", "voltage", "current", "power", "temperature"]]
            .rename(columns={
                "local_time": "Measurement time (Shanghai)",
                "voltage": "Voltage (V)",
                "current": "Current (A)",
                "power": "PV power (W)",
                "temperature": "Temperature (°C)",
            }),
            hide_index=True,
            use_container_width=True,
        )


render_dashboard(device_id, WINDOWS[window_label], temperature_limit, power_limit)
