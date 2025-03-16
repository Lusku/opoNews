import requests
import logging
import sqlite3
import os
import datetime
import asyncio
from bs4 import BeautifulSoup
from telegram import Bot

# Obtener las variables de entorno de GitHub Actions
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Verificar si las variables están definidas
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("❌ ERROR: La variable TELEGRAM_BOT_TOKEN no está configurada.")
if not TELEGRAM_CHAT_ID:
    raise ValueError("❌ ERROR: La variable TELEGRAM_CHAT_ID no está configurada.")


# Obtener la fecha actual
hoy = datetime.date.today()
url_boe = f"https://www.boe.es/boe/dias/{hoy.year}/{hoy.month:02}/{hoy.day:02}/"

# URLs oficiales para consultar información sobre la oposición
URLS_OPOSICION = {
    "BOE": url_boe,
    "Función Pública": "https://funcionpublica.digital.gob.es/va/funcion-publica/Acceso-Empleo-Publico/Convocatorias-Personal-Funcionario/Cuerpos-escalas-generales.html",
    "Ministerio de Hacienda": "https://www.hacienda.gob.es/es-ES/Empleo%20Publico/Paginas/EmpleoPublico.aspx",
    "INAP": "https://www.inap.es/en/cuerpo-superior-de-sistemas-y-tecnologias-de-la-informacion-de-la-administracion-del-estado"
}
# Configuración del logging
logging.basicConfig(level=logging.INFO)

# Conexión a la base de datos SQLite
DB_FILE = "oposiciones.db"

def crear_base_datos():
    """Crea la base de datos si no existe."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS noticias (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        fuente TEXT,
                        titulo TEXT UNIQUE,
                        enlace TEXT
                      )''')
    conn.commit()
    conn.close()

def obtener_noticias():
    """Consulta las fuentes oficiales y extrae noticias relevantes."""
    noticias = []

    for fuente, url in URLS_OPOSICION.items():
        try:
            respuesta = requests.get(url, timeout=10)
            if respuesta.status_code == 200:
                soup = BeautifulSoup(respuesta.text, "html.parser")

                # 🔹 Búsqueda en BOE
                if "boe.es" in url:
                    items = soup.find_all("li", class_="dispo")  # Selector correcto para BOE
                    for item in items:
                        titulo = item.find("p").text.strip() if item.find("p") else "Sin título"
                        enlace_tag = item.find("div", class_="enlacesDoc")
                        enlace = enlace_tag.find("a")["href"] if enlace_tag and enlace_tag.find("a") else url
                        if enlace.startswith("/"):
                            enlace = f"https://www.boe.es{enlace}"
                        noticias.append((fuente, titulo, enlace))

                # 🔹 Búsqueda en Función Pública
                elif "funcionpublica" in url:
                    tabla = soup.find("table")
                    filas = tabla.find("tbody").find_all("tr") if tabla else []
                    for fila in filas:
                        columnas = fila.find_all("td")
                        if len(columnas) >= 3:
                            titulo = columnas[0].text.strip()
                            grupo = columnas[1].text.strip()
                            oferta = columnas[2].text.strip()
                            mensaje = f"📢 *{titulo}* \n📌 Grupo: {grupo} \n📆 Oferta de Empleo Público: {oferta}"
                            noticias.append((fuente, mensaje, url))

                # 🔹 Búsqueda en INAP
                elif "inap.es" in url:
                    convocatorias = soup.find_all("h2", style="font-family: Helvetica Neue; Helvetica, Arial, sans-serif;")
                    for h2 in convocatorias:
                        año = h2.text.strip()
                        lista_enlaces = h2.find_next("ul")
                        if lista_enlaces:
                            enlaces = lista_enlaces.find_all("a")
                            for enlace in enlaces:
                                titulo = f"{año} - {enlace.text.strip()}"
                                url = enlace["href"]
                                if url.startswith("/"):
                                    url = f"https://www.inap.es{url}"
                                noticias.append(("INAP", titulo, url))
                                # 🔹 Búsqueda en Ministerio de Hacienda
                                
                elif "hacienda.gob.es" in url:
                    items = soup.find_all("a", class_="enlace-noticia")
                    for item in items:
                        titulo = item.text.strip()
                        enlace = item["href"] if item.has_attr("href") else url
                        noticias.append((fuente, titulo, enlace))
                        
        except requests.exceptions.RequestException as e:
            logging.error(f"❌ Error consultando {fuente}: {e}")

    return noticias


def filtrar_nuevas_noticias(noticias):
    """Verifica qué noticias son nuevas comparando con la base de datos."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    nuevas_noticias = []

    for fuente, titulo, enlace in noticias:
        cursor.execute("SELECT * FROM noticias WHERE titulo = ?", (titulo,))
        if cursor.fetchone() is None:  # Si no existe en la base de datos
            nuevas_noticias.append((fuente, titulo, enlace))
            cursor.execute("INSERT INTO noticias (fuente, titulo, enlace) VALUES (?, ?, ?)", (fuente, titulo, enlace))

    conn.commit()
    conn.close()
    return nuevas_noticias

async def enviar_mensaje_telegram(mensaje):
    """Envía un mensaje al grupo de Telegram y muestra depuración."""
    bot = Bot(token=TELEGRAM_BOT_TOKEN)

    logging.info(f"📢 Enviando mensaje a chat_id={TELEGRAM_CHAT_ID}")

    try:
        response = await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=mensaje, parse_mode="Markdown")
        logging.info(f"✅ Mensaje enviado con éxito: {response}")
    except Exception as e:
        logging.error(f"❌ Error al enviar mensaje: {e}")


def tarea_diaria():
    """Función principal que consulta, filtra y envía las actualizaciones."""
    noticias = obtener_noticias()
    nuevas_noticias = filtrar_nuevas_noticias(noticias)

    if nuevas_noticias:
        mensaje = "**📢 Nueva actualización sobre la oposición:**\n\n"
        for fuente, titulo, enlace in nuevas_noticias:
            mensaje += f"🔹 *{titulo}* \nFuente: {fuente} \n🔗 [Ver más]({enlace})\n\n"
    else:
        mensaje = "✅ No hay novedades en la oposición hoy."

    # Ejecutar la función async correctamente dentro de un loop
    asyncio.run(enviar_mensaje_telegram(mensaje))


# Ejecutar la tarea
if __name__ == "__main__":
    crear_base_datos()
    tarea_diaria()
