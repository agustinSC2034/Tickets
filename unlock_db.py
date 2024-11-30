import sqlite3

# Conexión a la base de datos
conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# Desbloquear la base de datos
cursor.execute("PRAGMA busy_timeout = 5000;")  # Espera hasta 5 segundos si está bloqueada
print("Base de datos desbloqueada.")

conn.close()

