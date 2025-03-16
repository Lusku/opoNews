import sqlite3

# Conectar a la base de datos
conn = sqlite3.connect("oposiciones.db")
cursor = conn.cursor()

# Consultar todas las noticias
cursor.execute("SELECT * FROM noticias")
datos = cursor.fetchall()

# Mostrar resultados
for fila in datos:
    print(fila)

# Cerrar conexión
conn.close()
