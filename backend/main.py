from fastapi.responses import JSONResponse, RedirectResponse
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
import mysql.connector

conn = mysql.connector.connect(
    host="localhost",
    user="root", 
    password="",  
    database="ristoranti",  
    port=3306
)

app = FastAPI()

baseSQL = """
SELECT 
	l.id id_locale,
	l.nome nome_locale,
	l.via via_locale,
	l.civico civico_locale,
	l.posti_max posti_max_locale,
	l.descrizione descrizione_locale,
	c.id id_comune,
	c.nome nome_comune,
	p.id id_provincia,
	p.nome nome_provincia,
	p.sigla sigla_provincia,
	r.id id_regione,
	r.nome nome_regione,
	a.cf cf_admin,
	a.password  password_admin,
	a.nome nome_admin,
	a.cognome cognome_admin,
	a.email email_admin,
	az.piva piva_azienda,
	az.nome nome_azienda,
	i.cf cf_imprenditore,
	i.nome nome_imprenditore,
	i.cognome cognome_imprenditore,
	i.telefono telefono_imprenditore,
	img.url img_url
    FROM locale l
	INNER JOIN comuni c ON c.id = l.id_comune  
	INNER JOIN province p  ON p.id  = c.id_provincia 
	INNER JOIN regioni r ON r.id = p.id_regione 
	INNER JOIN admin a ON a.id_locale = l.id 
	INNER JOIN azienda az ON az.piva = l.piva_azienda 
	INNER JOIN imprenditore i ON i.cf = az.cf_imprenditore
	INNER JOIN imgs img ON img.id_locale  = l.id
	INNER JOIN menu m ON m.id_locale = l.id 
	INNER JOIN piatto pi ON pi.id_menu = m.id
	"""





@app.get("/get_all_restaurants")
async def get_all(): 
    try: 
        cursor = conn.cursor(dictionary=True)
        query = baseSQL + "GROUP BY l.id"
        cursor.execute(query)
        result = cursor.fetchall()
        
        return JSONResponse(content = result)
    except mysql.connector.Error as err:
        return JSONResponse(content={"error": f"Errore nel recupero dei dati: {err}"})
    finally:
            cursor.close()

@app.post("/get_restaurant_from_id")
async def get_restaurant_from_id(request: Request):
    try:
        data = await request.json()
        cursor = conn.cursor(dictionary = True)
        id = data.get("id")
        query = baseSQL + "WHERE l.id = %s GROUP BY l.id"
        cursor.execute(query,(id,))
        
        result = cursor.fetchone()
        return JSONResponse(content = result)
    
    except mysql.connector.Error as err: 
        return JSONResponse(content={"Error": f"Errore nel recupero dei dati: {err}"})
    finally: 
        cursor.close()
    
    
# + group by l.id