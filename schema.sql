CREATE TABLE IF NOT EXISTS telemetry (
    id BIGSERIAL PRIMARY KEY,
    device_id VARCHAR(50) NOT NULL,
    measurement_timestamp TIMESTAMPTZ NOT NULL,
    received_timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    voltage DOUBLE PRECISION NOT NULL,
    current DOUBLE PRECISION NOT NULL,
    power DOUBLE PRECISION NOT NULL,
    temperature DOUBLE PRECISION NOT NULL,
    CONSTRAINT uq_telemetry_device_measurement
        UNIQUE (device_id, measurement_timestamp)
);
