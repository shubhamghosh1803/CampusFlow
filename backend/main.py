import os
import psycopg

from psycopg.rows import dict_row
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from enum import Enum
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="CampusFlow API", version="0.1.0")

def get_db_connection():
    return psycopg.connect(
        host= os.getenv("DB_HOST"),
        dbname= os.getenv("DB_NAME"),
        user= os.getenv("DB_USER"),
        password= os.getenv("DB_PASSWORD"),
        port= os.getenv("DB_PORT")
    )

class QueueRequest(BaseModel):
    service_id: int
    reason: str

class RequestStatus(str, Enum):
    WAITING = "Waiting"
    SERVING = "Serving"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"

class RequestPriority(str, Enum):
    NORMAL = "Normal"
    HIGH = "High"
    URGENT = "Urgent"

class UpdateRequest(BaseModel):
    status: RequestStatus
    priority: RequestPriority

allowed_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000,,http://127.0.0.1:5500,http://localhost:5500").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"message" : "Welcome to CampusFlow"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/db-test")
def db_test():
    connection = get_db_connection()
    connection.close()
    return {"message": "Database connection works"}

@app.get("/services")
def get_services():
    connection= get_db_connection()
    cursor= connection.cursor(row_factory=dict_row)

    cursor.execute(
        """
        select id,name,prefix
        from services
        order by id
        """
    )

    services= cursor.fetchall()
    cursor.close()
    connection.close()
    return {"services": services}

@app.get("/queue/{service_id}")
def get_queue(service_id: int):
    connection = get_db_connection();
    cursor = connection.cursor(row_factory=dict_row)

    cursor.execute(
        """
        select id, token, reason, status, priority, created_at,
        ROW_NUMBER() OVER (ORDER BY id) as position
        from queue_requests
        where service_id = %s
            and status in ('Waiting', 'Serving')
        order by id
        """,
        (service_id,)
    )

    queue = cursor.fetchall()

    for request in queue:
        request["people_ahead"] = request["position"] - 1

    cursor.close()
    connection.close()
    return {
        "service_id": service_id,
        "queue": queue
    }

@app.post("/queue/{service_id}/next")
def serve_next(service_id: int):
    connection = get_db_connection()
    cursor = connection.cursor(row_factory=dict_row)

    cursor.execute(
        """
        select id, token
        from queue_requests
        where service_id = %s and status = 'Serving'
        limit 1
        """,
        (service_id,)
    )

    current_serving = cursor.fetchone()

    if current_serving is not None:
        cursor.close()
        connection.close()
        raise HTTPException(status_code=409, detail=f"Request {current_serving['token']} is currently being served.")

    cursor.execute(
        """
        select id, token, reason, status, priority, created_at
        from queue_requests
        where service_id = %s and status = 'Waiting'
        order by
            case priority
                when 'Urgent' then 1
                when 'High' then 2
                when 'Normal' then 3
            END,
            id
        """,
        (service_id,)
    )

    next_request = cursor.fetchone()

    if next_request is None:
        cursor.close()
        connection.close()
        raise HTTPException(status_code=404, detail="No waiting requests in this queue")

    cursor.execute(
        """
        update queue_requests
        set status = 'Serving'
        where id = %s
        returning id, service_id, token, reason, status, priority, created_at
        """,
        (next_request["id"],)
    )

    served_request = cursor.fetchone()
    connection.commit()
    cursor.close()
    connection.close()

    return served_request

@app.patch("/queue/{request_id}/complete")
def complete_request(request_id: int):
    connection = get_db_connection()
    cursor = connection.cursor(row_factory=dict_row)

    cursor.execute(
        """
        update queue_requests
        set status = 'Completed'
        where id = %s and status = 'Serving'
        returning id, service_id, token, reason, status, priority, created_at
        """,
        (request_id,)
    )

    completed_request = cursor.fetchone()

    if completed_request is None:
        cursor.close()
        connection.close()
        raise HTTPException(status_code=404, detail="Request not found or not currently being served")

    connection.commit()
    cursor.close()
    connection.close()

    return completed_request

@app.post("/requests")
def create_request(request: QueueRequest):
    
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        select prefix from services where id = %s
        """,
        (request.service_id,)
    )


    service = cursor.fetchone()
    if service is None:
            cursor.close()
            connection.close()
            raise HTTPException(status_code=404, detail="Service not found")
    
    prefix= service[0]

    cursor.execute(
        """
        update services set next_token_number = next_token_number + 1
        where id = %s
        returning next_token_number
        """,
        (request.service_id, )
    )

    counter = cursor.fetchone()[0]

    token = f"{prefix}{counter}"

    cursor.execute(
         """
        insert into queue_requests(service_id, token, reason)
        values (%s, %s, %s)
        returning id
        """,
        (request.service_id, token, request.reason)
    )

    request_id = cursor.fetchone()[0]

    connection.commit()

    cursor.close()
    connection.close()

    return{
        "message": "Request Created",
        "request_id": request_id,
        "service_id" : request.service_id,
        "reason": request.reason,
        "token": token,
        "status": "Waiting"
    }

@app.patch("/requests/{request_id}/cancel")
def cancel_request(request_id: int):
    connection = get_db_connection()
    cursor = connection.cursor(row_factory=dict_row)

    cursor.execute(
        """
        UPDATE queue_requests
        SET status = 'Cancelled'
        WHERE id = %s AND status = 'Waiting'
        RETURNING id, service_id, token, reason, status, priority, created_at
        """,
        (request_id,)
    )

    cancelled_request = cursor.fetchone()

    if cancelled_request is None:
        cursor.close()
        connection.close()
        raise HTTPException(status_code=404, detail="Waiting request not found")

    connection.commit()
    cursor.close()
    connection.close()

    return cancelled_request

@app.get("/requests")
def get_requests():
    connection = get_db_connection()
    cursor = connection.cursor(row_factory=dict_row)

    cursor.execute(
        """
        SELECT id, service_id, token, reason, status, priority, created_at
        FROM queue_requests
        ORDER BY id
        """
    )

    requests = cursor.fetchall()

    cursor.close()
    connection.close()

    return {"requests": requests}

@app.get("/requests/{request_id}")
def get_request(request_id: int):
    connection = get_db_connection()
    cursor = connection.cursor(row_factory=dict_row)

    cursor.execute(
        """
        SELECT id, service_id, token, reason, status, priority, created_at
        FROM queue_requests
        WHERE id = %s
        """,
        (request_id,)
    )

    request = cursor.fetchone()

    cursor.close()
    connection.close()

    if request is None:
        raise HTTPException(status_code=404, detail="Request not found")

    return request

@app.patch("/requests/{request_id}")
def update_request(request_id: int, request: UpdateRequest):
    connection = get_db_connection()
    cursor = connection.cursor(row_factory=dict_row)

    cursor.execute(
        """
        UPDATE queue_requests
        SET status = %s, priority = %s
        WHERE id = %s
        RETURNING id, service_id, token, reason, status, priority, created_at
        """,
        (request.status, request.priority, request_id)
    )

    updated_request = cursor.fetchone()

    if updated_request is None:
        cursor.close()
        connection.close()
        raise HTTPException(status_code=404, detail="Request not found")

    connection.commit()
    cursor.close()
    connection.close()

    return updated_request

@app.patch("/requests/{request_id}/priority")
def update_priority(request_id: int, priority: RequestPriority):
    connection = get_db_connection()
    cursor = connection.cursor(row_factory=dict_row)

    cursor.execute(
        """
        UPDATE queue_requests
        SET priority = %s
        WHERE id = %s
          AND status = 'Waiting'
        RETURNING id, service_id, token, reason, status, priority, created_at
        """,
        (priority.value, request_id)
    )

    updated_request = cursor.fetchone()

    if updated_request is None:
        cursor.close()
        connection.close()
        raise HTTPException(
            status_code=404,
            detail="Waiting request not found"
        )

    connection.commit()

    cursor.close()
    connection.close()

    return updated_request

@app.delete("/requests/{request_id}")
def delete_request(request_id: int):
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        DELETE FROM queue_requests
        WHERE id = %s
        RETURNING id, token
        """,
        (request_id,)
    )

    deleted_request = cursor.fetchone()

    if deleted_request is None:
        cursor.close()
        connection.close()
        raise HTTPException(status_code=404, detail="Request not found")

    connection.commit()
    cursor.close()
    connection.close()

    return {"message": "Request deleted successfully",
            "request_id": deleted_request[0],
            "token": deleted_request[1]
    }
