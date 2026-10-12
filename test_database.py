
import os

import psycopg
from dotenv import load_dotenv


# .env dosyasındaki ortam değişkenlerini yükle
load_dotenv()


def main():
    # PostgreSQL bağlantı bilgilerini al
    connection_settings = {
        "host": os.getenv("DB_HOST"),
        "port": os.getenv("DB_PORT"),
        "dbname": os.getenv("DB_NAME"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "connect_timeout": 5,
    }

    try:
        # PostgreSQL sunucusuna bağlan
        with psycopg.connect(**connection_settings) as connection:
            with connection.cursor() as cursor:

                # Bağlandığımız veritabanını kontrol et
                cursor.execute("SELECT current_database();")
                database_name = cursor.fetchone()[0]

                # Telemetry tablosundaki kayıtları say
                cursor.execute("SELECT COUNT(*) FROM telemetry;")
                record_count = cursor.fetchone()[0]

                print("Database connection successful.")
                print(f"Database: {database_name}")
                print(f"Telemetry records: {record_count}")

    except psycopg.Error as error:
        print(f"Database connection failed: {error.__class__.__name__}")


if __name__ == "__main__":
    main()
