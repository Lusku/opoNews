import requests
import logging
import sqlite3
from bs4 import BeautifulSoup
from telegram import Bot

# Configuración del bot de Telegram
TELEGRAM_BOT_TOKEN = "TU_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID = "TU_CHAT_ID"

# URLs oficiales para consultar información sobre la oposición
URLS_OPOSICION = {
    "BOE": "https://www.boe.es/buscar/boe.php?campo%5B0%5D=TIT&dato%5B0%5D=cuerpo+superior+sistemas+tecnologías&operador%5B0%5D=and",
    "Ministerio de Hacienda": "https://www.hacienda.gob.es/es-ES/Empleo%20Publico/Paginas/EmpleoPublico.aspx",
    "INAP": "https://www.inap.es/oposiciones"
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

                # 🔹 Personalizar según la estructura de cada web 🔹
                if "boe.es" in url:
                    items = soup.find_all("div", class_="resultado-busqueda")  # Ejemplo
                elif "hacienda.gob.es" in url:
                    items = soup.find_all("a", class_="enlace-noticia")  # Ejemplo
                elif "inap.es" in url:
                    items = soup.find_all("li", class_="noticia")  # Ejemplo
                else:
                    items = []

                for item in items:
                    titulo = item.text.strip()
                    enlace = item.a["href"] if item.a else url  # Si no hay enlace, usar la URL base
                    noticias.append((fuente, titulo, enlace))

        except requests.exceptions.RequestException as e:
            logging.error(f"Error consultando {fuente}: {e}")

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

def enviar_mensaje_telegram(mensaje):
    """Envía un mensaje al canal de Telegram."""
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=mensaje, parse_mode="Markdown")

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

    enviar_mensaje_telegram(mensaje)

# Ejecutar la tarea
if __name__ == "__main__":
    crear_base_datos()
    tarea_diaria()
