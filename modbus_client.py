
import struct
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from pymodbus.client import ModbusTcpClient


HOST = "127.0.0.1"
PORT = 5020
READ_INTERVAL = 0.5

LOCAL_TIMEZONE = ZoneInfo("Asia/Shanghai")


# İki register'ı Float32 değerine dönüştür
def registers_to_float(registers):
    packed = struct.pack(">HH", *registers)
    return struct.unpack(">f", packed)[0]


# İki register'ı UInt32 tam sayıya dönüştür
def registers_to_uint32(registers):
    packed = struct.pack(">HH", *registers)
    return struct.unpack(">I", packed)[0]


def main():
    client = ModbusTcpClient(HOST, port=PORT)

    if not client.connect():
        print("Unable to connect to Modbus server.")
        return

    print("Connected to Modbus server.")

    previous_sequence = None

    try:
        while True:
            # Toplam 12 register oku
            response = client.read_holding_registers(
                address=0,
                count=12,
                device_id=1
            )

            if response.isError():
                print("Modbus read error.")
                time.sleep(READ_INTERVAL)
                continue

            registers = response.registers

            # Sensör değerlerini çözümle
            voltage = registers_to_float(registers[0:2])
            current = registers_to_float(registers[2:4])
            power = registers_to_float(registers[4:6])
            temperature = registers_to_float(registers[6:8])

            # Ölçüm zamanını ve sıra numarasını çözümle
            timestamp = registers_to_uint32(registers[8:10])
            sequence = registers_to_uint32(registers[10:12])

            measurement_time = datetime.fromtimestamp(
                timestamp,
                tz=timezone.utc
            ).astimezone(LOCAL_TIMEZONE)

            # Tekrar okunan veya atlanan ölçümleri kontrol et
            if previous_sequence is not None:
                if sequence == previous_sequence:
                    print("Warning: Duplicate sequence detected.")

                elif sequence > previous_sequence + 1:
                    missed = sequence - previous_sequence - 1
                    print(f"Warning: {missed} records skipped.")

                elif sequence < previous_sequence:
                    print("Warning: Sequence counter restarted.")

            previous_sequence = sequence

            print(
                f"Sequence: {sequence} | "
                f"Measurement Time: {measurement_time.isoformat()} | "
                f"Voltage: {voltage:.2f} V | "
                f"Current: {current:.2f} A | "
                f"Power: {power:.2f} W | "
                f"Temperature: {temperature:.2f} C"
            )

            time.sleep(READ_INTERVAL)

    except KeyboardInterrupt:
        print("\nModbus client stopped.")

    finally:
        client.close()


if __name__ == "__main__":
    main()
