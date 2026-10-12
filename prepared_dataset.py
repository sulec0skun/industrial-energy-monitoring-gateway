import pandas as pd

df = pd.read_csv("data/telemetry_sample.csv")

df["read_ts"] = pd.to_datetime(
    df["read_ts"],
    unit="s",
    utc=True
)
print("Total records:", len(df))

print("\nColumn names:")
print(df.columns.tolist())

print("\nFirst 5 telemetry records:")
print(df.head().to_string(index=False))

print("\nMeasurement period:")
print("Start:", df["read_ts"].min())
print("End:", df["read_ts"].max())
