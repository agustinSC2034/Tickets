from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import csv
from flask import Response
from werkzeug.security import check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from flask_mail import Mail, Message





# Conexión a la base de datos
def get_db_connection():
    conn = sqlite3.connect('database.db', timeout=10)  # Espera hasta 10 segundos si la base de datos está bloqueada
    conn.row_factory = sqlite3.Row
    return conn

# Inicializa Flask
app = Flask(__name__)
app.secret_key = 'inception'  # Agrega esta línea para habilitar sesiones seguras


# Configuración de Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'  # Servidor SMTP de Gmail (ajustar según el proveedor)
app.config['MAIL_PORT'] = 587  # Puerto para TLS
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'info@it-tel.com.ar'  # ✨ Reemplazá con el email real
app.config['MAIL_PASSWORD'] = 'vyva wxzr nuoz bhsv'  # ✨ "contraseña de aplicación"
app.config['MAIL_DEFAULT_SENDER'] = 'info@it-tel.com.ar'  # ✨ Debe ser el mismo email que el MAIL_USERNAME


mail = Mail(app)

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
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            login_user(User(id=user['id'], username=user['username'], role=user['role']))
            return redirect('/tickets')

        return "Correo o contraseña incorrectos"

    return render_template('login.html')




# Ruta para crear tickets
@app.route('/create_ticket', methods=['GET', 'POST'])
@login_required
def create_ticket():
    # Restringir acceso a usuarios con rol distinto de 'usittel'
    if current_user.role == 'usittel':
        return "Acceso denegado. Usittel no puede crear tickets.", 403

    if request.method == 'POST':
        tipo = request.form['tipo']
        descripcion = request.form['descripcion']
        prioridad = request.form['prioridad']
        usuario_creador = current_user.username

        conn = get_db_connection()
        conn.execute(
            'INSERT INTO tickets (tipo, descripcion, prioridad, usuario_creador) VALUES (?, ?, ?, ?)',
            (tipo, descripcion, prioridad, usuario_creador)
        )
        conn.commit()

        # Obtener emails de los administradores de Usittel
        usittel_users = conn.execute('SELECT email FROM users WHERE role = "usittel"').fetchall()
        conn.close()

        # Enviar correo a Usittel notificando la creación del ticket
        for user in usittel_users:
            send_email(user['email'], "Nuevo Ticket Creado",
                       f"Se ha creado un nuevo ticket de Directv con prioridad {prioridad}.")

        return redirect('/tickets')

    return render_template('create_ticket.html')




# Ruta para ver un ticket específico
@app.route('/ticket/<int:id>', methods=['GET'])
@login_required
def view_ticket(id):
    conn = get_db_connection()
    ticket = conn.execute('SELECT * FROM tickets WHERE id = ?', (id,)).fetchone()
    messages = conn.execute('SELECT * FROM messages WHERE ticket_id = ? ORDER BY fecha ASC', (id,)).fetchall()
    conn.close()

    if not ticket:
        return "Ticket no encontrado", 404

    return render_template('view_ticket.html', ticket=ticket, messages=messages, current_user=current_user)

# Ruta para agregar un mensaje a un ticket
@app.route('/add_message/<int:ticket_id>', methods=['POST'])
@login_required
def add_message(ticket_id):
    mensaje = request.form.get('mensaje')

    if not mensaje:
        return "Error: El mensaje no puede estar vacío.", 400

    conn = get_db_connection()
    conn.execute(
        'INSERT INTO messages (ticket_id, usuario, rol, mensaje, fecha) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)',
        (ticket_id, current_user.username, current_user.role, mensaje)
    )
    conn.commit()
    conn.close()

    return redirect(url_for('view_ticket', id=ticket_id))



# Ruta para listar tickets
@app.route('/tickets')
@login_required
def tickets():
    estado = request.args.get('estado')
    prioridad = request.args.get('prioridad')

    query = 'SELECT * FROM tickets WHERE 1=1'
    params = []

    if estado in ['pendiente', 'en proceso', 'cerrado']:
        query += ' AND estado = ?'
        params.append(estado)

    if prioridad in ['Baja', 'Media', 'Alta']:
        query += ' AND prioridad = ?'
        params.append(prioridad)

    conn = get_db_connection()
    tickets = conn.execute(query, params).fetchall()
    conn.close()

    return render_template('tickets.html', tickets=tickets, estado=estado, prioridad=prioridad)



# Actualizar tickets
@app.route('/ticket/<int:id>/update', methods=['POST'])
@login_required
def update_ticket(id):
    if current_user.role != 'usittel':
        return "Acceso denegado", 403

    nuevo_estado = request.form['estado']

    conn = get_db_connection()
    ticket = conn.execute('SELECT * FROM tickets WHERE id = ?', (id,)).fetchone()
    conn.execute('UPDATE tickets SET estado = ? WHERE id = ?', (nuevo_estado, id))
    conn.commit()

    # Obtener email del usuario creador del ticket (Directv)
    usuario_creador = ticket['usuario_creador']
    user = conn.execute('SELECT email FROM users WHERE username = ?', (usuario_creador,)).fetchone()
    conn.close()

    if user:
        send_email(user['email'], "Estado de tu ticket actualizado",
                   f"El estado de tu ticket #{id} ha cambiado a {nuevo_estado}")

    return redirect(url_for('view_ticket', id=id))



# Ruta para eliminar tickets
@app.route('/delete-ticket/<int:id>', methods=['POST'])
@login_required
def delete_ticket(id):
    if current_user.role != 'usittel':
        return "Acceso denegado", 403

    conn = get_db_connection()
    conn.execute('DELETE FROM tickets WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect('/tickets')


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


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']

        # Validaciones básicas
        if not email or not username or not password or not role:
            return "Todos los campos son obligatorios", 400

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        try:
            conn.execute(
                'INSERT INTO users (email, username, password, role) VALUES (?, ?, ?, ?)',
                (email, username, hashed_password, role)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            return "El email o el nombre de usuario ya existe.", 400
        finally:
            conn.close()

        return redirect('/login')

    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/login')  # Redirige al formulario de inicio de sesión


# Exportar tickets
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



# Cerrar tickets de parte de Directv
@app.route('/ticket/<int:id>/close', methods=['POST'])
@login_required
def close_ticket(id):
    conn = get_db_connection()
    ticket = conn.execute('SELECT * FROM tickets WHERE id = ?', (id,)).fetchone()

    if not ticket:
        return "El ticket no existe", 404

    if current_user.role not in ['directv', 'usittel']:
        return "Acceso denegado", 403

    conn.execute('UPDATE tickets SET estado = "cerrado" WHERE id = ?', (id,))
    conn.commit()

    # Notificar por correo electrónico a los usuarios correspondientes
    usittel_users = conn.execute('SELECT email FROM users WHERE role = "usittel"').fetchall()
    directv_users = conn.execute('SELECT email FROM users WHERE role = "directv"').fetchall()
    conn.close()

    # Enviar correos a los usuarios de Usittel si Directv cierra el ticket
    if current_user.role == 'directv':
        for user in usittel_users:
            send_email(user['email'], "Ticket cerrado", f"El ticket #{id} ha sido cerrado por Directv.")

    # Enviar correos a los usuarios de Directv si Usittel cierra el ticket
    if current_user.role == 'usittel':
        for user in directv_users:
            send_email(user['email'], "Ticket cerrado", f"El ticket #{id} ha sido cerrado por Usittel.")

    return redirect(url_for('view_ticket', id=id))



# historial ticket
@app.route('/ticket-history/<int:id>')
@login_required
def ticket_history(id):
    conn = get_db_connection()
    ticket = conn.execute('SELECT * FROM tickets WHERE id = ?', (id,)).fetchone()
    historial = conn.execute(
        'SELECT * FROM historial WHERE ticket_id = ? ORDER BY fecha DESC',
        (id,)
    ).fetchall()
    conn.close()

    if not ticket:
        return "El ticket no existe", 404

    return render_template('ticket_history.html', ticket=ticket, historial=historial)


# reabrir tickets
@app.route('/reopen_ticket/<int:id>', methods=['POST'])
@login_required
def reopen_ticket(id):
    if current_user.role != 'directv':
        return "Acceso denegado: Solo Directv puede reabrir un ticket.", 403

    conn = get_db_connection()

    # Verificar el estado actual del ticket
    ticket = conn.execute('SELECT estado FROM tickets WHERE id = ?', (id,)).fetchone()

    if not ticket or ticket['estado'].lower() not in ['resuelto', 'cerrado']:
        return "El ticket no está en un estado que permita reabrirse.", 400

    # Cambiar el estado del ticket a 'pendiente'
    conn.execute(
        'UPDATE tickets SET estado = ? WHERE id = ?',
        ('pendiente', id)
    )

    # Agregar un mensaje en el historial indicando que el ticket fue reabierto
    conn.execute(
        'INSERT INTO messages (ticket_id, usuario, rol, mensaje, fecha) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)',
        (id, current_user.username, current_user.role, "Ha reabierto el ticket.")
    )

    conn.commit()
    conn.close()

    return redirect(url_for('view_ticket', id=id))


def send_email(to, subject, message):
    try:
        msg = Message(subject, recipients=[to])
        msg.body = message
        mail.send(msg)
        print(f"Correo enviado a {to}: {subject}")
    except Exception as e:
        print(f"Error al enviar correo: {e}")




if __name__ == '__main__':
    app.run(debug=True)
