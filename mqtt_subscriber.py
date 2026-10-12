"""Store valid MQTT telemetry in PostgreSQL and publish a commit acknowledgment."""

import json
import math
import os
from datetime import datetime
from pathlib import Path

import paho.mqtt.client as mqtt
import psycopg
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

MQTT_HOST = "127.0.0.1"
MQTT_PORT = 1883
TELEMETRY_TOPIC = "energy/inverter_01/telemetry"
ACK_TOPIC = "energy/inverter_01/ack"


def validate_telemetry(data):
    # Zorunlu alanları ve gönderilen veri türlerini kontrol et
    if not isinstance(data, dict) or data.get("device_id") != "inverter_01":
        raise ValueError("Invalid device ID.")

    sequence = data.get("sequence_number")
    if type(sequence) is not int or sequence < 1:
        raise ValueError("Invalid sequence number.")

    measurement_time = datetime.fromisoformat(data["measurement_timestamp"])
    if measurement_time.tzinfo is None:
        raise ValueError("Measurement timestamp must include a timezone.")

    for column in ("voltage", "current", "power", "temperature"):
        if isinstance(data.get(column), bool) or not math.isfinite(float(data[column])):
            raise ValueError(f"Invalid {column} value.")

    return measurement_time


def save_telemetry(data, measurement_time):
    options = {
        "host": os.getenv("DB_HOST"),
        "port": os.getenv("DB_PORT"),
        "dbname": os.getenv("DB_NAME"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "connect_timeout": 5,
    }

    # Bağlantı context'i başarılıysa transaction commit edilir
    with psycopg.connect(**options) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO telemetry (
                    device_id, measurement_timestamp,
                    voltage, current, power, temperature
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (device_id, measurement_timestamp) DO NOTHING
                RETURNING id;
                """,
                (
                    data["device_id"], measurement_time,
                    data["voltage"], data["current"],
                    data["power"], data["temperature"],
                ),
            )
            row = cursor.fetchone()

    # Buraya gelindiyse commit başarılı (veya kayıt zaten vardı)
    return row[0] if row else None


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        client.subscribe(TELEMETRY_TOPIC, qos=1)
        print(f"Subscribed to: {TELEMETRY_TOPIC}")
    else:
        print(f"MQTT connection failed: {reason_code}")


def on_message(client, userdata, message):
    try:
        data = json.loads(message.payload.decode("utf-8"))
        measurement_time = validate_telemetry(data)
        record_id = save_telemetry(data, measurement_time)

        if record_id is None:
            print(f"Already saved: sequence {data['sequence_number']}")
        else:
            print(f"Saved telemetry record: {record_id}")

        # ACK yalnızca veritabanı işlemi başarılı olduktan sonra yayımlanır
        confirmation = {
            "device_id": data["device_id"],
            "measurement_timestamp": data["measurement_timestamp"],
            "sequence_number": data["sequence_number"],
        }
        result = client.publish(ACK_TOPIC, json.dumps(confirmation), qos=1)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            print("ACK publish failed; gateway will retry telemetry.")

    except (ValueError, KeyError, TypeError) as error:
        print(f"Invalid telemetry message: {error}")
    except psycopg.Error as error:
        print(f"Database temporarily unavailable: {type(error).__name__}")


def main():
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2, client_id="energy_db_subscriber"
    )
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        print("Starting MQTT database subscriber...")
        client.loop_forever()
    except KeyboardInterrupt:
        print("Subscriber stopped.")
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
