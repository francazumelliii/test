
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
@token_required
async def get_all():
    return {"message": "This is a protected route"}
    conn = get_db_connection()
    if not conn:
        return JSONResponse(content={"error": "Could not connect to the database"}, status_code=500)

    try:
        cursor = conn.cursor(dictionary=True)
        query = baseSQL + " GROUP BY l.id"
        cursor.execute(query)
        result = cursor.fetchall()
        return JSONResponse(content=result)
    except Error as err:
        logger.error(f"Error retrieving data: {err}")
        return JSONResponse(content={"error": f"Errore nel recupero dei dati: {err}"}, status_code=500)
    finally:
        cursor.close()
        conn.close()

@app.post("/get_restaurant_from_id")
@token_required
async def get_restaurant_from_id(request: Request):
    return {"message": "This is a protected route"}
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
@token_required
async def get_all_turns():
    return {"message": "This is a protected route"}
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
@token_required
async def check_tables(request: Request, data: TableCheckRequest):
    return {"message": "This is a protected route"}
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
@token_required
async def insert_reservation(request: Request):
    return {"message": "This is a protected route"}
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
@token_required
async def get_all_imgs(id: str = Query(..., description="ID locale")): 
    return {"message": "This is a protected route"}
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
@token_required
async def get_nearest(request: Request): 
    return {"message": "This is a protected route"}
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
@token_required
async def get_others(request: Request):
    await verify_token(request)
    return {"message": "This is a protected route"}
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
            
