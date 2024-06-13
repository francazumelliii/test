from fastapi import FastAPI, Request, HTTPException, Depends, Query, Header, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
import mysql.connector
import logging
from functools import wraps
from pydantic import BaseModel
import os
import secrets

app = FastAPI()

# Configurazione OAuth2
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Configurazione CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database connection details
db_config = {
    'host': "localhost",
    'user': "root",
    'password': "",
    'database': "ristoranti",
    'port': 3306
}

# Genera una chiave segreta casuale di lunghezza 32 byte (256 bit)
SECRET_KEY = secrets.token_urlsafe(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def get_db_connection():
    try:
        conn = mysql.connector.connect(**db_config)
        if conn.is_connected():
            return conn
    except mysql.connector.Error as e:
        logger.error(f"Error connecting to database: {e}")
    return None


class SignInRequest(BaseModel):
    email: str
    password: str


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"message": "Internal server error"}
    )


def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def verify_token(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return email
    except JWTError as e:
        raise HTTPException(status_code=401, detail="Invalid token")


@app.post("/signup")
async def signup(request: Request):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            return JSONResponse(content={"error": "Could not connect to the database"}, status_code=500)

        data = await request.json()
        name = data.get("name")
        surname = data.get("surname")
        email = data.get("email")
        password = data.get("password")

        if not name or not surname or not email or not password:
            return JSONResponse(content={"error": "Missing required fields"}, status_code=400)

        cursor = conn.cursor(dictionary=True)
        
        # Check if user already exists
        check_user_query = "SELECT * FROM cliente WHERE mail = %s"
        cursor.execute(check_user_query, (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            return JSONResponse(content={"error": "User with this email already exists"}, status_code=405)

        hashed_password = pwd_context.hash(password)

        # Insert new user
        insert_user_query = "INSERT INTO cliente (nome, cognome, mail, password) VALUES (%s, %s, %s, %s)"
        cursor.execute(insert_user_query, (name, surname, email, hashed_password))
        conn.commit()

        # Create JWT token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(data={"sub": email}, expires_delta=access_token_expires)

        return JSONResponse(content={"access_token": access_token, "token_type": "bearer"}, status_code=201)
    except mysql.connector.Error as err:
        return JSONResponse(content={"error": f"Error in retrieving data: {err}"}, status_code=500)
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.post("/signin")
async def signin(request: SignInRequest):
    conn = None
    cursor = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        query = "SELECT password FROM cliente WHERE mail = %s"
        cursor.execute(query, (request.email,))
        user = cursor.fetchone()

        if not user or not pwd_context.verify(request.password, user['password']):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(data={"sub": request.email}, expires_delta=access_token_expires)
        return {"access_token": access_token, "token_type": "bearer"}

    except mysql.connector.Error as db_err:
        logger.error(f"Database error: {db_err}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.post("/verify_token")
async def verify_token_route(authorization: str = Header(None)):
    if authorization is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authorization scheme")
        
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        return {"valid": True}
    except JWTError as e:
        raise HTTPException(status_code=401, detail="Invalid token")


# Base SQL query
baseSQL = """
SELECT 
    l.id AS id_locale,
    l.nome AS nome_locale,
    l.via AS via_locale,
    l.civico AS civico_locale,
    l.posti_max AS posti_max_locale,
    l.descrizione AS descrizione_locale,
    l.banner AS banner_locale,
    c.id AS id_comune,
    c.nome AS nome_comune,
    p.id AS id_provincia,
    p.nome AS nome_provincia,
    p.sigla AS sigla_provincia,
    r.id AS id_regione,
    r.nome AS nome_regione,
    a.cf AS cf_admin,
    a.password AS password_admin,
    a.nome AS nome_admin,
    a.cognome AS cognome_admin,
    a.email AS email_admin,
    az.piva AS piva_azienda,
    az.nome AS nome_azienda,
    i.cf AS cf_imprenditore,
    i.nome AS nome_imprenditore,
    i.cognome AS cognome_imprenditore,
    i.telefono AS telefono_imprenditore,
    img.url AS img_url
FROM locale l
INNER JOIN comuni c ON c.id = l.id_comune  
INNER JOIN province p ON p.id = c.id_provincia 
INNER JOIN regioni r ON r.id = p.id_regione 
INNER JOIN admin a ON a.id_locale = l.id 
INNER JOIN azienda az ON az.piva = l.piva_azienda 
INNER JOIN imprenditore i ON i.cf = az.cf_imprenditore
INNER JOIN imgs img ON img.id_locale = l.id
INNER JOIN menu m ON m.id_locale = l.id 
INNER JOIN piatto pi ON pi.id_menu = m.id

"""

@app.get("/get_all_restaurants")
async def get_all_restaurants(request: Request, token: str = Depends(verify_token)):
    logger.info("Attempting to retrieve all restaurants...")
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        cursor = conn.cursor(dictionary=True)
        cursor.execute(baseSQL + "GROUP BY l.id")
        results = cursor.fetchall()
        
        if not results:
            logger.info("No restaurants found")
            return JSONResponse(content={"message": "No restaurants found"}, status_code=200)
        
        return JSONResponse(content=results, status_code=200)
    except mysql.connector.Error as err:
        logger.error(f"Database error: {err}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.get("/search_restaurants")
async def search_restaurants(
    nome_locale: str = Query(None), 
    nome_comune: str = Query(None), 
    nome_provincia: str = Query(None), 
    nome_regione: str = Query(None), 
    token: str = Depends(verify_token)
):
    logger.info(f"Searching restaurants with criteria - locale: {nome_locale}, comune: {nome_comune}, provincia: {nome_provincia}, regione: {nome_regione}")
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        cursor = conn.cursor(dictionary=True)
        query = baseSQL + " WHERE 1=1"
        params = []
        
        if nome_locale:
            query += " AND l.nome LIKE %s"
            params.append(f"%{nome_locale}%")
        if nome_comune:
            query += " AND c.nome LIKE %s"
            params.append(f"%{nome_comune}%")
        if nome_provincia:
            query += " AND p.nome LIKE %s"
            params.append(f"%{nome_provincia}%")
        if nome_regione:
            query += " AND r.nome LIKE %s"
            params.append(f"%{nome_regione}%")
        
        query += "GROUP BY locale.id"
        cursor.execute(query, tuple(params))
        results = cursor.fetchall()
        
        if not results:
            logger.info("No restaurants found with given criteria")
            return JSONResponse(content={"message": "No restaurants found with given criteria"}, status_code=200)
        
        return JSONResponse(content= results, status_code=200)
    except mysql.connector.Error as err:
        logger.error(f"Database error: {err}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.post("/get_restaurant_from_id")

async def get_restaurant_from_id(request: Request, token: str = Depends(verify_token)):
    conn = get_db_connection()
    if not conn:
        return JSONResponse(content={"error": "Could not connect to the database"}, status_code=500)

    try:
        data = await request.json()
        id = data.get("id")
        if not id:
            return JSONResponse(content={"error": "Missing parameter: id"}, status_code=400)

        cursor = conn.cursor(dictionary=True)
        query = baseSQL + " WHERE l.id = %s GROUP BY l.id"
        cursor.execute(query, (id,))
        result = cursor.fetchone()
        if result:
            return JSONResponse(content=result)
        else:
            return JSONResponse(content={"message": "No data found"}, status_code=404)
    except Error as err:
        logger.error(f"Error retrieving data: {err}")
        return JSONResponse(content={"error": f"Errore nel recupero dei dati: {err}"}, status_code=500)
    finally:
        cursor.close()
        conn.close()

@app.get("/ping")
async def ping():
    return JSONResponse(content="pong")

@app.get("/turns")

async def get_all_turns(request: Request, token: str = Depends(verify_token)):

    conn = get_db_connection()
    if not conn:
        return JSONResponse(content={"error": "Could not connect to the database"}, status_code=500)

    try:
        cursor = conn.cursor(dictionary=True)
        query = "SELECT id, TIME_FORMAT(ora_inizio, '%H:%i:%s') AS ora_inizio, TIME_FORMAT(ora_fine, '%H:%i:%s') AS ora_fine FROM turno"
        cursor.execute(query)
        result = cursor.fetchall()
        return JSONResponse(content=result)
    except Error as err:
        logger.error(f"Error retrieving data: {err}")
        return JSONResponse(content={"error": f"Errore nel recupero dei dati: {err}"}, status_code=500)
    finally:
        cursor.close()
        conn.close()


class TableCheckRequest(BaseModel):
    date: str
    turn: int
    id: int
    
    
@app.post("/check_tables")

async def check_tables(request: Request, data: TableCheckRequest,token: str = Depends(verify_token)):
    try:
        conn = get_db_connection()
        if not conn:
            return JSONResponse(content={"error": "Could not connect to the database"}, status_code=500)
        cursor = conn.cursor()

        query = """
        SELECT 
            SUM(prenota.num_posti) AS total_reserved,
            locale.posti_max AS max
        FROM 
            locale 
        LEFT JOIN 
            prenota ON prenota.id_locale = locale.id AND prenota.data = %s AND prenota.id_turno = %s
        WHERE 
            locale.id = %s
        GROUP BY 
            locale.posti_max
        """

        cursor.execute(query, (data.date, data.turn, data.id))
        result = cursor.fetchone()

        if not result:
            # Se non ci sono prenotazioni per questo locale, restituisci solo il numero massimo di posti
            max_seats_query = """
            SELECT posti_max FROM locale WHERE id = %s
            """
            cursor.execute(max_seats_query, (data.id,))
            max_seats_result = cursor.fetchone()
            if max_seats_result:
                return JSONResponse(content={"available_seats": max_seats_result[0]}, status_code=200)
            else:
                return JSONResponse(content={"message": "No results found"}, status_code=200)

        # Calcola i posti disponibili
        total_reserved = result[0] or 0  # Se total_reserved è None, assegna 0
        max_seats = result[1] or 0  # Se max_seats è None, assegna 0
        available_seats = max_seats - total_reserved

        return JSONResponse(content={"available_seats": available_seats}, status_code=200)

    except Error as err:
        logging.error(f"Error retrieving data: {err}")
        return JSONResponse(content={"error": f"Error retrieving data: {err}"}, status_code=500)
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()



@app.post("/insert_reservation")

async def insert_reservation(request: Request, token: str = Depends(verify_token)):
    try:
        data = await request.json()
        conn = get_db_connection()
        id, turn, date, qt, email = data.get("id"), data.get("turn"), data.get("date"), data.get("qt"), data.get("email")
        cursor = conn.cursor(dictionary=True)
        query = "INSERT INTO prenota VALUES (%s,%s,%s,%s,%s)"
        cursor.execute(query, (email, id, date, qt, turn))
        conn.commit()  # Assicurati di eseguire il commit per salvare le modifiche nel database
        return JSONResponse(content={"message": "Reservation successfully inserted"},status_code=200)
    except mysql.connector.Error as err:
        return JSONResponse(content={"error": f"Error in retrieving data: {err}"}, status_code=500)
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.get("/imgs")

async def get_all_imgs(id: str = Query(..., description="ID locale"), token: str = Depends(verify_token)): 
    try: 
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        query = "SELECT * FROM imgs WHERE id_locale = %s"
        cursor.execute(query, (id,))
        result = cursor.fetchall()
        return JSONResponse(content = result)
    except mysql.connector.Error as err:
        return JSONResponse(content={"Error": f"Error in retrieving data: {err}"},status_code=400)
        
    finally: 
        cursor.close()
        conn.close()
        
@app.post("/get_nearest")

async def get_nearest(request: Request, token: str = Depends(verify_token)): 
    try: 
        conn = get_db_connection()
        data = await request.json()
        cursor = conn.cursor(dictionary=True)
        
        village = data.get("village")
        county = data.get("county")
        state = data.get("state")
        

        query = baseSQL + " WHERE "
        
        conditions = []
        if village:
            conditions.append(f"c.nome LIKE '{village}'")
        if county:
            conditions.append(f"p.nome LIKE '{county}'")
        if state:
            conditions.append(f"r.nome LIKE '{state}'")
        
        # Unisci le condizioni con AND
        query += " AND ".join(conditions)
        query += " GROUP BY l.id"
        
        cursor.execute(query)
        result = cursor.fetchall()
        
        return result
        
    except mysql.connector.Error as err:
        return JSONResponse(content={"Error": f"Error in retrieving data: {err}"},status_code=400)
    finally: 
        cursor.close()
        conn.close()
        
        
@app.post("/get_others")

async def get_others(request: Request, token: str = Depends(verify_token)):
    conn = None
    cursor = None
    try:
        data = await request.json()
        ids = data.get("ids")
        village = data.get("village")
        county = data.get("county")
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Constructing the SQL query
        query = baseSQL + """
         WHERE (p.nome = %s OR c.nome = %s)
        AND l.id NOT IN ({}) GROUP BY l.id
        """.format(','.join(['%s'] * len(ids)))

        params = [county, village] + ids

        cursor.execute(query, params)
        result = cursor.fetchall()

        return JSONResponse(content=result)
    except mysql.connector.Error as err:
        return JSONResponse(content={"Error": f"Error in retrieving data: {err}"}, status_code=400)
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            
