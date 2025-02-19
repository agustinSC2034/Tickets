from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import csv
import io
from flask import Response
from werkzeug.security import check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask import send_from_directory
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

        if user:
            if user['suspended'] == 1:
                return "Cuenta suspendida. Contacta con el administrador."

            if check_password_hash(user['password'], password):
                login_user(User(id=user['id'], username=user['username'], role=user['role']))
                return redirect('/tickets')

        return "Correo o contraseña incorrectos"

    return render_template('login.html')





# Ruta para crear tickets
# Ruta para crear tickets
@app.route('/create_ticket', methods=['GET', 'POST'])
@login_required
def create_ticket():
    if current_user.role == 'usittel':
        flash("Acceso denegado. Usittel no puede crear tickets.", "error")
        return redirect(url_for('tickets'))

    if request.method == 'POST':
        tipo = request.form['tipo']
        descripcion = request.form['descripcion']
        prioridad = request.form['prioridad']
        usuario_creador = current_user.username

        conn = get_db_connection()
        conn.execute(
            'INSERT INTO tickets (tipo, descripcion, prioridad, usuario_creador, fecha_creacion) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)',
            (tipo, descripcion, prioridad, usuario_creador)
        )
        conn.commit()

        # Obtener emails de los administradores de Usittel
        usittel_users = conn.execute('SELECT email FROM users WHERE role = "usittel"').fetchall()
        conn.close()

        # Enviar notificación de éxito
        flash("Ticket creado exitosamente.", "success")

        # Enviar notificación por correo a Usittel
        for user in usittel_users:
            send_email(user['email'], "Nuevo Ticket Creado",
                       f"Se ha creado un nuevo ticket:\n\n"
                       f"Tipo: {tipo}\n"
                       f"Prioridad: {prioridad}\n"
                       f"Descripción: {descripcion}\n\n"
                       f"Creado por: {usuario_creador}")

        return redirect(url_for('tickets'))

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
import os
from werkzeug.utils import secure_filename

# Configurar carpeta de almacenamiento
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Verificar si el archivo es válido
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Modificar la función de agregar mensajes
@app.route('/add_message/<int:ticket_id>', methods=['POST'])
@login_required
def add_message(ticket_id):
    mensaje = request.form.get('mensaje')
    archivo = request.files.get('archivo')
    archivo_nombre = None

    conn = get_db_connection()
    ticket = conn.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()

    if not ticket:
        conn.close()
        flash("El ticket no existe.", "error")
        return redirect(url_for('tickets'))

    # Guardar archivo si se sube uno válido
    if archivo and allowed_file(archivo.filename):
        archivo_nombre = secure_filename(archivo.filename)
        archivo.save(os.path.join(app.config['UPLOAD_FOLDER'], archivo_nombre))

    # Insertar el mensaje en la base de datos con el archivo adjunto
    conn.execute(
        'INSERT INTO messages (ticket_id, usuario, rol, mensaje, archivo_adjunto, fecha) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)',
        (ticket_id, current_user.username, current_user.role, mensaje, archivo_nombre)
    )
    conn.commit()

    # Notificar a la otra empresa
    if current_user.role == 'usittel':
        destinatarios = [row['email'] for row in conn.execute("SELECT email FROM users WHERE role = 'directv'").fetchall()]
    else:
        destinatarios = [row['email'] for row in conn.execute("SELECT email FROM users WHERE role = 'usittel'").fetchall()]

    conn.close()

    # Enviar correo a todos los destinatarios
    asunto = f"Nuevo mensaje en el Ticket #{ticket_id}"
    mensaje_correo = f"El usuario {current_user.username} ha agregado un mensaje en el ticket #{ticket_id}:\n\n{mensaje}"

    for email in destinatarios:
        send_email(email, asunto, mensaje_correo)

    flash("Mensaje enviado correctamente.", "success")
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

    query += ' ORDER BY fecha_creacion DESC'  # Ordenar por fecha de creación (más nuevos arriba)

    conn = get_db_connection()
    tickets = conn.execute(query, params).fetchall()
    conn.close()

    return render_template('tickets.html', tickets=tickets, estado=estado, prioridad=prioridad)




# Actualizar tickets
# Actualizar tickets
@app.route('/ticket/<int:id>/update', methods=['POST'])
@login_required
def update_ticket(id):
    if current_user.role != 'usittel':
        flash("Acceso denegado", "error")
        return redirect(url_for('tickets'))

    nuevo_estado = request.form['estado']

    conn = get_db_connection()
    ticket = conn.execute('SELECT * FROM tickets WHERE id = ?', (id,)).fetchone()

    if not ticket:
        flash("El ticket no existe.", "error")
        return redirect(url_for('tickets'))

    # Actualizar el estado del ticket
    conn.execute('UPDATE tickets SET estado = ? WHERE id = ?', (nuevo_estado, id))

    # Guardar mensaje en el chat indicando el cambio de estado
    mensaje_estado = f"{current_user.username} ha cambiado el estado del ticket a {nuevo_estado}."
    conn.execute(
        'INSERT INTO messages (ticket_id, usuario, rol, mensaje, fecha) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)',
        (id, current_user.username, current_user.role, mensaje_estado)
    )

    conn.commit()

    # Enviar notificación de éxito
    flash(f"Estado del ticket #{id} actualizado a {nuevo_estado}.", "success")

    # Notificar a la empresa opuesta al creador del ticket
    if current_user.role == 'usittel':
        destinatarios = [row['email'] for row in conn.execute("SELECT email FROM users WHERE role = 'directv'").fetchall()]
    else:
        destinatarios = [row['email'] for row in conn.execute("SELECT email FROM users WHERE role = 'usittel'").fetchall()]

    conn.close()

    # Enviar correo a todos los destinatarios
    asunto = f"Estado del Ticket #{id} actualizado"
    mensaje = f"El usuario {current_user.username} ha cambiado el estado del ticket #{id} a '{nuevo_estado}'."

    for email in destinatarios:
        send_email(email, asunto, mensaje)

    return redirect(url_for('view_ticket', id=id))


@app.route('/delete-user/<int:id>', methods=['POST'])
@login_required
def delete_user(id):
    if current_user.role != 'usittel':
        flash("Acceso denegado.", "error")
        return redirect(url_for('users'))

    conn = get_db_connection()
    conn.execute('DELETE FROM users WHERE id = ?', (id,))
    conn.commit()
    conn.close()

    flash("Usuario eliminado correctamente.", "success")
    return redirect(url_for('users'))




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

@app.route('/users')
@login_required
def users():
    if current_user.role != 'usittel':
        flash("Acceso denegado.", "error")
        return redirect(url_for('tickets'))

    conn = get_db_connection()
    users = conn.execute('SELECT id, username, email, role, suspended FROM users').fetchall()

    conn.close()

       # Agrega esta línea para depuración
    print("Usuarios cargados:", users)

    return render_template('users.html', users=users)


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
@login_required
def export_tickets():
    conn = get_db_connection()
    
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

    tickets = conn.execute(query, params).fetchall()
    conn.close()

    # Crear archivo CSV en memoria
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)


    # Escribir encabezados
    writer.writerow(["ID", "Tipo", "Descripción", "Prioridad", "Estado", "Fecha de creación", "Usuario creador"])

    # Escribir los datos de los tickets
    for ticket in tickets:
        writer.writerow([
            ticket['id'],
            ticket['tipo'],
            ticket['descripcion'],
            ticket['prioridad'],
            ticket['estado'],
            ticket['fecha_creacion'],
            ticket['usuario_creador']
        ])

    response = Response(output.getvalue().encode('utf-8-sig'), mimetype='text/csv; charset=utf-8')
    response.headers.set('Content-Disposition', 'attachment', filename='tickets.csv')
    
    return response






# Ruta para cerrar un ticket
@app.route('/ticket/<int:id>/close', methods=['POST'])
@login_required
def close_ticket(id):
    conn = get_db_connection()
    ticket = conn.execute('SELECT * FROM tickets WHERE id = ?', (id,)).fetchone()

    if not ticket:
        flash("El ticket no existe.", "error")
        return redirect(url_for('tickets'))

    if current_user.role not in ['directv', 'usittel']:
        flash("Acceso denegado.", "error")
        return redirect(url_for('tickets'))

    # Cerrar ticket
    conn.execute('UPDATE tickets SET estado = "cerrado" WHERE id = ?', (id,))
    
    # Guardar mensaje en el chat
    mensaje_cierre = f"{current_user.username} ha cerrado el ticket."
    conn.execute(
        'INSERT INTO messages (ticket_id, usuario, rol, mensaje, fecha) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)',
        (id, current_user.username, current_user.role, mensaje_cierre)
    )

    conn.commit()

        # Notificar a la empresa opuesta
    if current_user.role == 'directv':
        destinatarios = [row['email'] for row in conn.execute("SELECT email FROM users WHERE role = 'usittel'").fetchall()]
    else:
        destinatarios = [row['email'] for row in conn.execute("SELECT email FROM users WHERE role = 'directv'").fetchall()]

    conn.close()

    # Enviar correo a todos los destinatarios
    asunto = f"Ticket #{id} cerrado"
    mensaje = f"El ticket #{id} ha sido cerrado por {current_user.username}."

    for email in destinatarios:
        send_email(email, asunto, mensaje)


    flash(f"Ticket #{id} cerrado correctamente.", "success")
    return redirect(url_for('view_ticket', id=id))


@app.route('/test-notification')
def test_notification():
    flash("¡Esta es una notificación de prueba!", "success")
    return redirect(url_for('tickets'))



# reabrir tickets
@app.route('/reopen_ticket/<int:id>', methods=['POST'])
@login_required
def reopen_ticket(id):
    if current_user.role != 'directv':
        flash("Acceso denegado: Solo Directv puede reabrir un ticket.", "error")
        return redirect(url_for('tickets'))

    conn = get_db_connection()
    ticket = conn.execute('SELECT estado FROM tickets WHERE id = ?', (id,)).fetchone()

    if not ticket or ticket['estado'].lower() != 'cerrado':
        flash("El ticket no está en un estado que permita reabrirse.", "error")
        return redirect(url_for('tickets'))

    # Cambiar el estado a 'pendiente'
    conn.execute('UPDATE tickets SET estado = ? WHERE id = ?', ('pendiente', id))

    # Mensaje automático en el historial
    mensaje_reapertura = f"{current_user.username} ha reabierto el ticket."
    conn.execute('INSERT INTO messages (ticket_id, usuario, rol, mensaje, fecha) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)',
                 (id, current_user.username, current_user.role, mensaje_reapertura))

    conn.commit()
    
    # Notificar a Usittel
    usittel_users = conn.execute('SELECT email FROM users WHERE role = "usittel"').fetchall()
    conn.close()

    for user in usittel_users:
        send_email(user['email'], "Ticket reabierto",
                   f"El ticket #{id} ha sido reabierto por Directv.")

    # 🔥 Agregar notificación de éxito
    flash(f"El ticket #{id} ha sido reabierto correctamente.", "success")  # Verde para éxito

    return redirect(url_for('view_ticket', id=id))


# Ruta para editar un usuario
@app.route('/edit-user/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_user(id):
    if current_user.role != 'usittel':
        flash("Acceso denegado.", "error")
        return redirect(url_for('users'))

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (id,)).fetchone()

    if not user:
        conn.close()
        flash("Usuario no encontrado.", "error")
        return redirect(url_for('users'))

    if request.method == 'POST':
        new_username = request.form['username']
        email = request.form['email']
        role = request.form['role']

        # Guardamos el nombre anterior para actualizarlo en tickets
        old_username = user['username']

        # Actualizar datos del usuario en la tabla users
        conn.execute(
            'UPDATE users SET username = ?, email = ?, role = ? WHERE id = ?',
            (new_username, email, role, id)
        )

        # Actualizar el nombre en la tabla tickets
        conn.execute(
            'UPDATE tickets SET usuario_creador = ? WHERE usuario_creador = ?',
            (new_username, old_username)
        )

        conn.commit()
        conn.close()

        flash("Usuario actualizado correctamente.", "success")
        return redirect(url_for('users'))

    conn.close()
    return render_template('edit_user.html', user=user)


# Ruta para suspender un usuario
@app.route('/suspend_user/<int:id>', methods=['POST'])
@login_required
def suspend_user(id):
    if current_user.role != 'usittel':
        flash("Acceso denegado", "error")
        return redirect(url_for('users'))

    conn = get_db_connection()
    user = conn.execute('SELECT id, suspended FROM users WHERE id = ?', (id,)).fetchone()

    if not user:
        flash("Usuario no encontrado.", "error")
        return redirect(url_for('users'))

    new_status = 1 if user['suspended'] == 0 else 0  # Alternar estado
    conn.execute('UPDATE users SET suspended = ? WHERE id = ?', (new_status, id))
    conn.commit()
    conn.close()

    flash(f"Usuario {'suspendido' if new_status == 1 else 'activado'} correctamente.", "success")
    return redirect(url_for('users'))



# Ruta para activar un usuario suspendido
@app.route('/activate-user/<int:id>', methods=['POST'])
@login_required
def activate_user(id):
    if current_user.role != 'usittel':
        flash("Acceso denegado.", "error")
        return redirect(url_for('users'))

    conn = get_db_connection()
    conn.execute('UPDATE users SET suspended = 0 WHERE id = ?', (id,))
    conn.commit()
    conn.close()

    flash("Usuario activado correctamente.", "success")
    return redirect(url_for('users'))



from flask import send_from_directory



# Configurar carpeta de almacenamiento
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Crear la carpeta 'uploads' si no existe
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


@app.route('/uploads/<filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


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
