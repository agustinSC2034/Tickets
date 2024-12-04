from flask import Flask, render_template, request, redirect
import sqlite3
import csv
from flask import Response
from flask_login import login_user
from werkzeug.security import check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash


# Conexión a la base de datos
def get_db_connection():
    conn = sqlite3.connect('database.db', timeout=10)  # Espera hasta 10 segundos si la base de datos está bloqueada
    conn.row_factory = sqlite3.Row
    return conn

# Inicializa Flask
app = Flask(__name__)
app.secret_key = 'inception'  # Agrega esta línea para habilitar sesiones seguras


# Configurar Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Redirige a /login si no estás autenticado


# Clase User para manejar la autenticación
class User(UserMixin):
    def __init__(self, id, username, role):
        self.id = id
        self.username = username
        self.role = role

# Función para cargar el usuario desde la base de datos
@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()

    if user:
        return User(id=user['id'], username=user['username'], role=user['role'])
    return None



# Ruta principal
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            login_user(User(id=user['id'], username=user['username'], role=user['role']))
            return redirect('/tickets')  # Redirige a la lista de tickets después de iniciar sesión
        return "Usuario o contraseña incorrectos"

    return render_template('login.html')



# Ruta para crear tickets
@app.route('/create-ticket', methods=['GET', 'POST'])
def create_ticket():
    if request.method == 'POST':
        tipo = request.form.get('tipo')
        descripcion = request.form.get('descripcion')
        prioridad = request.form.get('prioridad')
        usuario = request.form.get('usuario')

        # Validación
        if not tipo or not descripcion or not prioridad or not usuario:
            return "Error: Todos los campos son obligatorios.", 400

        # Guarda en la base de datos
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
    estado = request.args.get('estado')  # Filtrar por estado
    prioridad = request.args.get('prioridad')  # Filtrar por prioridad

    query = 'SELECT * FROM tickets WHERE 1=1'
    params = []

    if estado:
        query += ' AND estado = ?'
        params.append(estado)

    if prioridad:
        query += ' AND prioridad = ?'
        params.append(prioridad)

    conn = get_db_connection()
    tickets = conn.execute(query, params).fetchall()
    conn.close()

    return render_template('tickets.html', tickets=tickets, estado=estado, prioridad=prioridad)

@app.route('/update-ticket/<int:id>', methods=['POST'])
def update_ticket(id):
    nuevo_estado = request.form.get('nuevo_estado')

    if not nuevo_estado:
        return "Error: El estado es obligatorio.", 400

    conn = get_db_connection()
    try:
        conn.execute(
            'UPDATE tickets SET estado = ? WHERE id = ?',
            (nuevo_estado, id)
        )
        conn.execute(
            'INSERT INTO historial (ticket_id, accion) VALUES (?, ?)',
            (id, f"Cambio de estado a '{nuevo_estado}'")
        )
        conn.commit()
    finally:
        conn.close()

    return "Estado actualizado exitosamente. <a href='/tickets'>Volver a la lista de tickets</a>"




# Ruta para eliminar tickets
@app.route('/delete-ticket/<int:id>', methods=['POST'])
def delete_ticket(id):
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM tickets WHERE id = ?', (id,))
        conn.commit()
    finally:
        conn.close()
    return "Ticket eliminado exitosamente. <a href='/tickets'>Volver a la lista de tickets</a>"



@app.route('/ticket/<int:id>')
def ticket_details(id):
    conn = get_db_connection()
    ticket = conn.execute('SELECT * FROM tickets WHERE id = ?', (id,)).fetchone()
    historial = conn.execute('SELECT * FROM historial WHERE ticket_id = ? ORDER BY fecha DESC', (id,)).fetchall()
    conn.close()
    return render_template('ticket_details.html', ticket=ticket, historial=historial)


@app.route('/assign-ticket/<int:id>', methods=['POST'])
def assign_ticket(id):
    usuario_asignado = request.form.get('usuario_asignado')

    if not usuario_asignado:
        return "Error: El usuario asignado es obligatorio.", 400

    conn = get_db_connection()
    conn.execute(
        'UPDATE tickets SET usuario_asignado = ? WHERE id = ?',
        (usuario_asignado, id)
    )
    conn.commit()
    conn.close()

    return "Usuario asignado exitosamente. <a href='/tickets'>Volver a la lista de tickets</a>"



# Ruta para la logica de la nota en Flask
@app.route('/add-note/<int:id>', methods=['POST'])
def add_note(id):
    nota = request.form.get('nota')

    if not nota:
        return "Error: La nota no puede estar vacía.", 400

    conn = get_db_connection()
    try:
        # Usa || para concatenar notas con un salto de línea
        conn.execute(
            "UPDATE tickets SET notas = COALESCE(notas, '') || ? WHERE id = ?",
            (f"\n{nota}", id)
        )
        conn.commit()
    finally:
        conn.close()

    return f"Nota agregada exitosamente. <a href='/ticket/{id}'>Volver al ticket</a>"


@app.route('/export-tickets', methods=['GET'])
def export_tickets():
    import io
    conn = get_db_connection()
    tickets = conn.execute('SELECT * FROM tickets').fetchall()
    conn.close()

    # Crear el archivo CSV en memoria
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    # Escribir encabezados
    writer.writerow(["ID", "Tipo", "Descripción", "Prioridad", "Estado", "Fecha de creación", "Usuario creador", "Usuario asignado", "Notas"])

    # Escribir los datos de los tickets
    for ticket in tickets:
        writer.writerow([
            ticket['id'],
            ticket['tipo'],
            ticket['descripcion'],
            ticket['prioridad'],
            ticket['estado'],
            ticket['fecha_creacion'],
            ticket['usuario_creador'],
            ticket['usuario_asignado'] if ticket['usuario_asignado'] else "",
            ticket['notas'].replace("\n", " ") if ticket['notas'] else ""
        ])

    # Convertir el CSV a bytes con codificación UTF-8
    response = Response(output.getvalue().encode('utf-8-sig'), mimetype='text/csv; charset=utf-8')
    response.headers.set('Content-Disposition', 'attachment', filename='tickets.csv')
    return response







if __name__ == '__main__':
    app.run(debug=True)
