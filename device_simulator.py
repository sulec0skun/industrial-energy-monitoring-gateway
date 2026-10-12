"""Replay real inverter measurements through Modbus with database-backed acknowledgments."""

import asyncio
import json
import struct
from pathlib import Path

import pandas as pd
from pymodbus.datastore import (
    ModbusDeviceContext,
    ModbusSequentialDataBlock,
    ModbusServerContext,
)
from pymodbus.server import StartAsyncTcpServer

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "telemetry_sample.csv"
STATE_FILE = BASE_DIR / "data" / "simulator_state.json"

HOST = "127.0.0.1"
PORT = 5020
REPLAY_DELAY_SECONDS = 0.2
ACK_POLL_SECONDS = 0.05

MEASUREMENTS = ("pv1volt", "pv1curr", "pv1power", "temper1")


def float_to_registers(value):
    # Float32 sayısını iki adet 16 bit Modbus register'ına dönüştür
    return list(struct.unpack(">HH", struct.pack(">f", float(value))))


def uint32_to_registers(value):
    # Pozitif tam sayıyı iki Modbus register'ına dönüştür
    return list(struct.unpack(">HH", struct.pack(">I", int(value))))


def registers_to_uint32(values):
    return struct.unpack(">I", struct.pack(">HH", *values))[0]


def load_next_index(record_count):
    if not STATE_FILE.exists():
        return 0
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    index = state["next_index"]
    if type(index) is not int or not 0 <= index <= record_count:
        raise ValueError("Invalid simulator checkpoint.")
    return index


def save_next_index(index):
    # Önce geçici dosyaya yaz, sonra atomik olarak asıl dosyanın yerine koy
    temporary = STATE_FILE.with_suffix(".json.tmp")
    temporary.write_text(json.dumps({"next_index": index}), encoding="utf-8")
    temporary.replace(STATE_FILE)


def build_registers(record, sequence):
    result = []
    for column in MEASUREMENTS:
        result.extend(float_to_registers(record[column]))

    # Veri setindeki orijinal UTC zaman damgasını taşı
    measurement_time = pd.to_datetime(record["timestamp_utc"], utc=True)
    result.extend(uint32_to_registers(int(measurement_time.timestamp())))
    result.extend(uint32_to_registers(sequence))
    return result


async def replay_data(device, dataframe):
    start = load_next_index(len(dataframe))
    print(f"Loaded {len(dataframe)} measurements. Completed: {start}.")

    for index in range(start, len(dataframe)):
        record = dataframe.iloc[index]
        sequence = index + 1

        # Yeni kayıt başlamadan önce önceki ACK değerini temizle
        device.setValues(3, 12, [0, 0])
        device.setValues(3, 0, build_registers(record, sequence))
        print(f"Waiting for database ACK: {sequence}/{len(dataframe)}")

        while True:
            acknowledged = registers_to_uint32(device.getValues(3, 12, count=2))
            if acknowledged == sequence:
                # Sadece veritabanı onayından sonra ilerlemeyi sakla
                save_next_index(index + 1)
                print(f"Database confirmed: {sequence}/{len(dataframe)}")
                break
            await asyncio.sleep(ACK_POLL_SECONDS)

        await asyncio.sleep(REPLAY_DELAY_SECONDS)

    # Son ACK sonrasında register dizisini boşalt
    device.setValues(3, 10, [0, 0])
    device.setValues(3, 12, [0, 0])
    print("Replay complete: all measurements acknowledged.")
    # Sunucu açık kalır ama artık yeni kayıt üretilmez


async def main():
    if not DATA_FILE.is_file():
        raise FileNotFoundError(f"Dataset not found: {DATA_FILE}")
    dataframe = pd.read_csv(DATA_FILE)
    required = [*MEASUREMENTS, "timestamp_utc"]
    if dataframe.empty or dataframe[required].isna().any().any():
        raise ValueError("Dataset is empty or contains missing telemetry fields.")

    device = ModbusDeviceContext(hr=ModbusSequentialDataBlock(0, [0] * 32))
    context = ModbusServerContext(devices=device, single=True)

    print(f"Modbus server listening on {HOST}:{PORT}")
    await asyncio.gather(
        StartAsyncTcpServer(context=context, address=(HOST, PORT)),
        replay_data(device, dataframe),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Device simulator stopped.")
