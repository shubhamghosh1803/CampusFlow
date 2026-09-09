import os
import psycopg

connection = psycopg.connect(
    host= os.getenv("DB_HOST", "localhost"),
    dbname= os.getenv("DB_NAME", "CampusFlow"),
    user= os.getenv("DB_USER", "postgres"),
    password= os.getenv("DB_PASSWORD"),
    port= os.getenv("DB_PORT","5432")
)

print("Database connection established successfully !!")

connection.close()