import os
import time
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'super_clave_secreta_so1')

DB_HOST = os.environ.get('DB_HOST', 'db')
DB_NAME = os.environ.get('POSTGRES_DB', 'proyecto_sistemas_operativos_db')
DB_USER = os.environ.get('POSTGRES_USER', 'admin')
DB_PASS = os.environ.get('POSTGRES_PASSWORD', 'admin123')

def get_db_connection():
    retries = 5
    while retries > 0:
        try:
            conn = psycopg2.connect(
                host=DB_HOST,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASS,
                cursor_factory=RealDictCursor
            )
            return conn
        except psycopg2.OperationalError:
            retries -= 1
            time.sleep(2)
    raise Exception("No se pudo conectar a la base de datos PostgreSQL")

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    # Tabla de usuarios
    cur.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL
        );
    ''')
    # Tabla de articulos
    cur.execute('''
        CREATE TABLE IF NOT EXISTS articulos (
            id SERIAL PRIMARY KEY,
            titulo VARCHAR(150) NOT NULL,
            contenido TEXT NOT NULL,
            usuario_id INT REFERENCES usuarios(id) ON DELETE CASCADE
        );
    ''')
    conn.commit()
    cur.close()
    conn.close()

# Inicializar DB al arrancar
try:
    init_db()
except Exception as e:
    print(f"Error inicializando base de datos: {e}")

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO usuarios (username, password) VALUES (%s, %s);", (username, hashed_password))
            conn.commit()
            flash('Usuario registrado exitosamente. Por favor inicia sesión.', 'success')
            return redirect(url_for('login'))
        except psycopg2.IntegrityError:
            conn.rollback()
            flash('El nombre de usuario ya existe.', 'danger')
        finally:
            cur.close()
            conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM usuarios WHERE username = %s;", (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('dashboard'))
        else:
            flash('Usuario o contraseña incorrectos.', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM articulos WHERE usuario_id = %s ORDER BY id DESC;", (session['user_id'],))
    articulos = cur.fetchall()
    cur.close()
    conn.close()

    # Identificador del contenedor para demostración de balanceo de carga
    hostname = os.uname()[1]
    return render_template('dashboard.html', articulos=articulos, hostname=hostname)

@app.route('/articulo/crear', methods=['POST'])
def crear_articulo():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    titulo = request.form['titulo'].strip()
    contenido = request.form['contenido'].strip()

    if titulo and contenido:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO articulos (titulo, contenido, usuario_id) VALUES (%s, %s, %s);",
                    (titulo, contenido, session['user_id']))
        conn.commit()
        cur.close()
        conn.close()
        flash('Artículo creado con éxito.', 'success')

    return redirect(url_for('dashboard'))

@app.route('/articulo/editar/<int:id>', methods=['POST'])
def editar_articulo(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    titulo = request.form['titulo'].strip()
    contenido = request.form['contenido'].strip()

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE articulos SET titulo = %s, contenido = %s WHERE id = %s AND usuario_id = %s;",
                (titulo, contenido, id, session['user_id']))
    conn.commit()
    cur.close()
    conn.close()
    flash('Artículo actualizado correctamente.', 'success')

    return redirect(url_for('dashboard'))

@app.route('/articulo/eliminar/<int:id>', methods=['POST'])
def eliminar_articulo(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM articulos WHERE id = %s AND usuario_id = %s;", (id, session['user_id']))
    conn.commit()
    cur.close()
    conn.close()
    flash('Artículo eliminado.', 'warning')

    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)