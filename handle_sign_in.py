import os
import psycopg2
from flask import Flask, request, jsonify, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import random

app = Flask(__name__)

# =========================================
# CONFIGURACIÓN DE SESIÓN (CRÍTICO)
# =========================================
app.secret_key = "cambia_esto_por_una_clave_secreta_segura_123456"
# Modifica estas líneas en tu handle_sign_in.py
app.config.update(
    SESSION_COOKIE_SECURE=False,      
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax", # Cambiado de None a Lax para evitar bloqueos en navegadores
    PERMANENT_SESSION_LIFETIME=3600
)

# Cambia la configuración de CORS por esta más robusta
CORS(app, resources={
    r"/*": {
        "origins": "*", # Permite cualquier origen, incluyendo 'null' de archivos locales
        "supports_credentials": True
    }
})

DATABASE_URL = "postgresql://neondb_owner:npg_AGfr1VQl2dib@ep-restless-lab-al6gks8u-pooler.c-3.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)


# =========================================
# REGISTRO
# =========================================
@app.route("/register", methods=["POST", "OPTIONS"])
def handle_register():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
        
    data = request.get_json()
    username = data.get("usuario")
    email = data.get("email")
    password = data.get("password")
    nombre = data.get("nombre")
    apellido = data.get("apellido")
    
    if not username or not password or not email:
        return jsonify({"error": "Faltan campos obligatorios"}), 400
    
    user_id = random.randint(1, 1000000)
    password_hash = generate_password_hash(password)
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM usuario WHERE username = %s OR email = %s", (username, email))
        if cursor.fetchone():
            return jsonify({"error": "El usuario o email ya está registrado"}), 409
        
        cursor.execute("""
            INSERT INTO usuario (id, username, email, password_hash, nombre, apellido) 
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, username, email, nombre, apellido
        """, (user_id, username, email, password_hash, nombre, apellido))
        
        new_user = cursor.fetchone()
        conn.commit()
        
        return jsonify({
            "success": True,
            "message": "Usuario registrado correctamente"
        }), 201
        
    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        return jsonify({"error": f"Error de base de datos: {str(e)}"}), 500
        
    finally:
        if conn:
            cursor.close()
            conn.close()


# =========================================
# LOGIN
# =========================================
@app.route("/login", methods=["POST", "OPTIONS"])
def handle_login():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
        
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")
    
    if not email or not password:
        return jsonify({"error": "Faltan email o contraseña"}), 400
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, username, email, password_hash, nombre, apellido 
            FROM usuario WHERE email = %s
        """, (email,))
        
        user = cursor.fetchone()
        
        if not user:
            return jsonify({"error": "Usuario no encontrado"}), 404
        
        if not check_password_hash(user[3], password):
            return jsonify({"error": "Contraseña incorrecta"}), 401
        
        # =========================================
        # GUARDAR EN SESIÓN (CRÍTICO)
        # =========================================
        session["user_id"] = user[0]
        session["username"] = user[1]
        session["nombre"] = user[4]
        session.permanent = True  # Hacer la sesión permanente
        
        # =========================================
        # ↓↓↓ TU ENLACE DE REDIRECCIÓN ↓↓↓
        # =========================================
        redirect_url = "formulario_personalizacion_guitarra.html"
        # =========================================
        
        return jsonify({
            "success": True,
            "message": "Login exitoso",
            "redirect": redirect_url,
            "user": {
                "id": user[0],
                "username": user[1],
                "nombre": user[4],
                "apellido": user[5]
            }
        }), 200
        
    except psycopg2.Error as e:
        return jsonify({"error": f"Error de base de datos: {str(e)}"}), 500
        
    finally:
        if conn:
            cursor.close()
            conn.close()


# =========================================
# OBTENER USUARIO ACTUAL (¡FALTABA @app.route!)
# =========================================
@app.route("/me", methods=["GET", "OPTIONS"])
def get_current_user():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
        
    if "user_id" not in session:
        return jsonify({"logged_in": False}), 200
    
    return jsonify({
        "logged_in": True,
        "user": {
            "id": session["user_id"],
            "username": session.get("username"),
            "nombre": session.get("nombre")
        }
    }), 200


# =========================================
# CERRAR SESIÓN
# =========================================
@app.route("/logout", methods=["POST", "OPTIONS"])
def logout():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
        
    session.clear()
    return jsonify({"message": "Sesión cerrada"})


@app.route("/")
def index():
    return jsonify({"message": "GuitarBuilder Pro API"})

    # Añade esto a tu archivo handle_sign_in.py

@app.route("/pedido", methods=["POST", "OPTIONS"])
def crear_pedido():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    # Verificar si el usuario está logueado
    if "user_id" not in session:
        return jsonify({"error": "Debes iniciar sesión para realizar un pedido"}), 401

    data = request.get_json()
    user_id = session["user_id"]
    
    # Extraer datos del JSON enviado por el JS
    # Nota: Asegúrate de que los nombres coincidan con los que envías en el JS
    cuerpo = data.get("cuerpo")
    pastillas = data.get("pastillas")
    acabado = data.get("acabado")
    precio = data.get("precio")
    detalles = data.get("detalles") # Aquí puedes meter la config de pastillas, colores, etc.

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Insertar en la tabla pedido (ajusta los nombres de columnas a tu DB real)
        cursor.execute("""
            INSERT INTO pedido (usuario_id, cuerpo, pastillas, acabado, precio, detalles)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (user_id, cuerpo, pastillas, acabado, precio, detalles))
        
        nuevo_id = cursor.fetchone()[0]
        conn.commit()
        
        return jsonify({
            "success": True, 
            "message": "Pedido guardado con éxito",
            "pedido_id": nuevo_id
        }), 201

    except Exception as e:
        if conn: conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            cursor.close()
            conn.close()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)