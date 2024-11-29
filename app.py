from flask import Flask, render_template, request
import sqlite3

app = Flask(__name__)

# Conexión a la base de datos
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row  # Esto hace que los resultados se comporten como diccionarios
    return conn

# Ruta principal
@app.route('/')
def home():
    return render_template('index.html')

# Ruta para crear tickets
@app.route('/create-ticket', methods=['GET', 'POST'])
def create_ticket():
    if request.method == 'POST':
        # Captura los datos del formulario
        tipo = request.form['tipo']
        descripcion = request.form['descripcion']
        prioridad = request.form['prioridad']
        usuario = request.form['usuario']

        # Guarda el ticket en la base de datos
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO tickets (tipo, descripcion, prioridad, usuario_creador) VALUES (?, ?, ?, ?)',
            (tipo, descripcion, prioridad, usuario)
        )
        conn.commit()
        conn.close()

        return "Ticket creado exitosamente"  # Mensaje temporal

    return render_template('create_ticket.html')

# Ruta para listar tickets
@app.route('/tickets')
def tickets():
    conn = get_db_connection()
    tickets = conn.execute('SELECT * FROM tickets').fetchall()
    conn.close()
    return render_template('tickets.html', tickets=tickets)

if __name__ == '__main__':
    app.run(debug=True)


