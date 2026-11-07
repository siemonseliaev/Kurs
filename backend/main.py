import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import psycopg2

app = FastAPI()

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "db"),
        database=os.getenv("DB_NAME", "event_platform_db"),
        user=os.getenv("DB_USER", "event_user"),
        password=os.getenv("DB_PASSWORD", "secure_password")
    )

# Автоматическое создание таблиц при запуске бэкенда
@app.on_event("startup")
def startup_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            day VARCHAR(10) NOT NULL,
            hour INT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS registrations (
            id SERIAL PRIMARY KEY,
            event_id INT REFERENCES events(id) ON DELETE CASCADE,
            participant_name VARCHAR(255) NOT NULL,
            participant_email VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

class EventCreate(BaseModel):
    name: str
    day: str
    hour: int

class RegistrationCreate(BaseModel):
    event_id: int
    name: str
    email: str

@app.get("/api/events")
def get_events():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, day, hour FROM events;")
    events = [{"id": row[0], "name": row[1], "day": row[2], "hour": row[3]} for row in cur.fetchall()]
    cur.close()
    conn.close()
    return events

@app.post("/api/events")
def create_event(event: EventCreate):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO events (name, day, hour) VALUES (%s, %s, %s) RETURNING id;", (event.name, event.day, event.hour))
    event_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return {"id": event_id, **event.dict()}

@app.post("/api/register")
def register_for_event(reg: RegistrationCreate):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM events WHERE id = %s;", (reg.event_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="Мероприятие не найдено")
    
    cur.execute(
        "INSERT INTO registrations (event_id, participant_name, participant_email) VALUES (%s, %s, %s);",
        (reg.event_id, reg.name, reg.email)
    )
    conn.commit()
    cur.close()
    conn.close()
    return {"status": "success", "message": "Вы успешно зарегистрированы!"}

@app.delete("/api/events/{event_id}")
def delete_event(event_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Проверяем, существует ли мероприятие
    cur.execute("SELECT id FROM events WHERE id = %s;", (event_id,))
    if not cur.fetchone():
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Мероприятие не найдено")
    
    # Благодаря ON DELETE CASCADE в базе автоматически удалятся и связанные записи на мероприятие
    cur.execute("DELETE FROM events WHERE id = %s;", (event_id,))
    conn.commit()
    cur.close()
    conn.close()
    return {"status": "success", "message": "Мероприятие удалено"}