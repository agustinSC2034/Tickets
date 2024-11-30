import sqlite3

# Conexión a la base de datos
connection = sqlite3.connect('database.db')
cursor = connection.cursor()

# Agregar columna 'usuario_asignado' si no existe
try:
    cursor.execute('ALTER TABLE tickets ADD COLUMN usuario_asignado TEXT')
    print("Columna 'usuario_asignado' agregada exitosamente.")
except sqlite3.OperationalError:
    print("La columna 'usuario_asignado' ya existe.")

# Agregar columna 'notas' si no existe
try:
    cursor.execute('ALTER TABLE tickets ADD COLUMN notas TEXT')
    print("Columna 'notas' agregada exitosamente.")
except sqlite3.OperationalError:
    print("La columna 'notas' ya existe.")

# Guardar cambios y cerrar conexión
connection.commit()
connection.close()
