"""Bridge Modbus measurements to MQTT and acknowledge records only after database commit."""

import json
import queue
import struct
import time
from datetime import datetime, timezone
from threading import Event

import paho.mqtt.client as mqtt
from pymodbus.client import ModbusTcpClient

MODBUS_HOST = "127.0.0.1"
MODBUS_PORT = 5020
MQTT_HOST = "127.0.0.1"
MQTT_PORT = 1883
TELEMETRY_TOPIC = "energy/inverter_01/telemetry"
ACK_TOPIC = "energy/inverter_01/ack"
DEVICE_ID = "inverter_01"

POLL_SECONDS = 0.05
RETRY_SECONDS = 3.0


def registers_to_float(values):
    return struct.unpack(">f", struct.pack(">HH", *values))[0]


def registers_to_uint32(values):
    return struct.unpack(">I", struct.pack(">HH", *values))[0]


def uint32_to_registers(value):
    return list(struct.unpack(">HH", struct.pack(">I", int(value))))


def read_measurement(client):
    response = client.read_holding_registers(address=0, count=12, device_id=1)
    if response.isError():
        raise RuntimeError("Modbus read failed.")

    values = response.registers
    sequence = registers_to_uint32(values[10:12])
    if sequence == 0:
        return None

    timestamp = registers_to_uint32(values[8:10])
    return {
        "device_id": DEVICE_ID,
        "measurement_timestamp": datetime.fromtimestamp(
            timestamp, tz=timezone.utc
        ).isoformat(),
        "sequence_number": sequence,
        "voltage": round(registers_to_float(values[0:2]), 2),
        "current": round(registers_to_float(values[2:4]), 2),
        "power": round(registers_to_float(values[4:6]), 2),
        "temperature": round(registers_to_float(values[6:8]), 2),
    }


def main():
    acknowledgments = queue.Queue()
    subscribed = Event()

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            client.subscribe(ACK_TOPIC, qos=1)
        else:
            print(f"MQTT connection failed: {reason_code}")

    def on_subscribe(client, userdata, mid, reason_codes, properties):
        if reason_codes and any(code.is_failure for code in reason_codes):
            print("MQTT ACK subscription was rejected.")
            return
        subscribed.set()
        print("Subscribed to database acknowledgments.")

    def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
        subscribed.clear()
        print("MQTT disconnected; waiting to reconnect.")

    def on_message(client, userdata, message):
        try:
            ack = json.loads(message.payload.decode("utf-8"))
            if ack.get("device_id") == DEVICE_ID:
                acknowledgments.put(ack)
        except (ValueError, AttributeError):
            print("Invalid database ACK ignored.")

    publisher = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="energy_gateway")
    publisher.on_connect = on_connect
    publisher.on_subscribe = on_subscribe
    publisher.on_disconnect = on_disconnect
    publisher.on_message = on_message

    modbus = ModbusTcpClient(MODBUS_HOST, port=MODBUS_PORT)

    try:
        publisher.connect(MQTT_HOST, MQTT_PORT, 60)
        publisher.loop_start()
        if not subscribed.wait(timeout=10):
            raise RuntimeError("MQTT ACK subscription timed out.")

        while not modbus.connect():
            print("Waiting for Modbus server...")
            time.sleep(2)

        print("Gateway started. Awaiting database acknowledgments.")
        pending_key = None
        next_retry_at = 0.0

        while True:
            try:
                telemetry = read_measurement(modbus)
            except Exception as error:
                print(f"Modbus unavailable: {type(error).__name__}")
                modbus.close()
                time.sleep(1)
                modbus.connect()
                continue

            if telemetry is None:
                time.sleep(POLL_SECONDS)
                continue

            key = (telemetry["sequence_number"], telemetry["measurement_timestamp"])
            if key != pending_key:
                pending_key = key
                next_retry_at = 0.0

            # ACK yalnızca aynı sıra ve ölçüm zamanına aitse geçerli
            while not acknowledgments.empty():
                ack = acknowledgments.get_nowait()
                if (
                    ack.get("sequence_number"),
                    ack.get("measurement_timestamp"),
                ) != pending_key:
                    continue

                reply = modbus.write_registers(
                    address=12,
                    values=uint32_to_registers(telemetry["sequence_number"]),
                    device_id=1,
                )
                if reply.isError():
                    print("Unable to forward ACK to inverter.")
                else:
                    print(f"Database ACK forwarded: {telemetry['sequence_number']}")
                    next_retry_at = time.monotonic() + RETRY_SECONDS

            if subscribed.is_set() and time.monotonic() >= next_retry_at:
                telemetry["published_timestamp"] = datetime.now(
                    timezone.utc
                ).isoformat()
                publish_info = publisher.publish(
                    TELEMETRY_TOPIC, json.dumps(telemetry), qos=1
                )
                if publish_info.rc == mqtt.MQTT_ERR_SUCCESS:
                    print(f"Published sequence {telemetry['sequence_number']}")
                else:
                    print("Publish could not be queued; will retry.")
                next_retry_at = time.monotonic() + RETRY_SECONDS

            time.sleep(POLL_SECONDS)

    except KeyboardInterrupt:
        print("Gateway stopped.")
    finally:
        modbus.close()
        publisher.disconnect()
        publisher.loop_stop()


if __name__ == "__main__":
    main()
