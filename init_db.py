import sqlite3

# Conexión a la base de datos
connection = sqlite3.connect('database.db')

# Crear la tabla de tickets
with open('schema.sql') as f:
    connection.executescript(f.read())

connection.commit()
connection.close()

