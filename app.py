from flask import Flask, request, jsonify, send_from_directory, abort
import pyodbc
import os

# --- 1. CONFIGURACIÓN DEL ENTORNO ---

# Importante: Usamos el nombre del servidor EXACTO de tu SQL Management Studio
SERVER = 'ACER-NITRO-16\\SQLEXPRESS' 
DATABASE = 'PRUEBAS'

# Opción A (Predeterminada, requiere instalación del driver 17)
DRIVER_NAME = 'ODBC Driver 17 for SQL Server'
# Opción B (Alternativa, driver genérico y más común)
# DRIVER_NAME = 'SQL Server' 

CONNECTION_STRING = (
    f'DRIVER={{{DRIVER_NAME}}};'  # El nombre del driver va entre tres llaves {}
    f'SERVER={SERVER};'
    f'DATABASE={DATABASE};'
    'Trusted_Connection=yes;'
)
STATIC_FOLDER = 'global'

app = Flask(__name__)

# Función auxiliar para ejecutar comandos SQL (Insert, Update, Delete)
def execute_db_command(sql, params):
    try:
        conn = pyodbc.connect(CONNECTION_STRING)
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        conn.close()
        return True, None
    except pyodbc.Error as ex:
        # Devuelve el error de la base de datos
        return False, str(ex)

# --- 2. RUTAS DE NAVEGACIÓN (HTML) ---

# Ruta principal: Carga la página de Skills (index.html)
@app.route('/')
def serve_main_skills():
    return send_from_directory(STATIC_FOLDER, 'index.html')

# Ruta de Login: Carga el formulario de login (login.html)
@app.route('/login.html')
def serve_login():
    return send_from_directory(STATIC_FOLDER, 'login.html')

# Ruta de Edición: Carga el panel de edición (edit_skills.html)
@app.route('/edit_skills.html')
def serve_edit_skills():
    return send_from_directory(STATIC_FOLDER, 'edit_skills.html')

# Ruta para archivos estáticos (CSS, JS, imágenes, etc.)
@app.route('/<path:filename>')
def serve_static_files(filename):
    try:
        return send_from_directory(STATIC_FOLDER, filename)
    except FileNotFoundError:
        abort(404)


# --- 3. ENDPOINTS DE API (CRUD de SKILLS) ---

# ENDPOINT: Leer todas las Skills (GET /api/skills)
@app.route('/api/skills', methods=['GET'])
def get_skills():
    try:
        conn = pyodbc.connect(CONNECTION_STRING)
        cursor = conn.cursor()
        
        # CORRECCIÓN CLAVE: Agregamos WHERE SkillType IS NOT NULL para evitar errores de agrupación
        sql = "SELECT SkillType, SkillName, SkillID AS Id FROM dbo.Skills WHERE SkillType IS NOT NULL ORDER BY SkillType, SkillName"
        cursor.execute(sql)
        
        # 2. Agrupamos los resultados en un diccionario: {"Tipo": [skill1, skill2], ...}
        grouped_skills = {}
        for row in cursor.fetchall():
            skill_type = row[0] 
            skill_name = row[1] 
            skill_id = row[2] 
            
            if skill_type not in grouped_skills:
                grouped_skills[skill_type] = []
                
            grouped_skills[skill_type].append({'Id': skill_id, 'SkillName': skill_name})
            
        conn.close()
        
        return jsonify(grouped_skills), 200
        
    except pyodbc.Error as ex:
        return jsonify({'error': f"Error de DB: {str(ex)}"}), 500

# ENDPOINT: Borrar Skill (POST /api/skills/delete)
@app.route('/api/skills/delete', methods=['POST'])
def delete_skill():
    skill_id = request.get_json().get('Id')
    # Usa SkillID que es el nombre correcto de la columna
    sql = "DELETE FROM dbo.Skills WHERE SkillID = ?" 
    
    success, error = execute_db_command(sql, (skill_id,))
    if success:
        return jsonify({'success': True}), 200
    else:
        return jsonify({'success': False, 'message': f"No se pudo borrar: {error}"}), 500

# ENDPOINT: Agregar Skill (POST /api/skills/add)
@app.route('/api/skills/add', methods=['POST'])
def add_skill():
    data = request.get_json()
    new_name = data.get('SkillName')
    new_type = data.get('SkillType') 
    
    if not new_name or not new_type:
        return jsonify({'success': False, 'message': 'Nombre y Tipo de Skill son requeridos.'}), 400

    sql = "INSERT INTO dbo.Skills (SkillName, SkillType) VALUES (?, ?)"
    
    success, error = execute_db_command(sql, (new_name, new_type))
    if success:
        return jsonify({'success': True}), 201
    else:
        return jsonify({'success': False, 'message': f"No se pudo agregar: {error}"}), 500

# ENDPOINT: Actualizar Skill (POST /api/skills/update)
@app.route('/api/skills/update', methods=['POST'])
def update_skill():
    data = request.get_json()
    skill_id = data.get('Id')
    new_name = data.get('SkillName')
    new_type = data.get('SkillType') 

    if not new_type:
        # Actualización solo de nombre
        sql = "UPDATE dbo.Skills SET SkillName = ? WHERE SkillID = ?"
        params = (new_name, skill_id)
    else:
        # Versión completa si se incluye SkillType
        sql = "UPDATE dbo.Skills SET SkillName = ?, SkillType = ? WHERE SkillID = ?"
        params = (new_name, new_type, skill_id)
    
    success, error = execute_db_command(sql, params)
    if success:
        return jsonify({'success': True}), 200
    else:
        return jsonify({'success': False, 'message': f"No se pudo actualizar: {error}"}), 500


# ENDPOINT: Autenticación (POST /api/login)
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('UserName')
    password = data.get('Password')
    
    if not username or not password:
        return jsonify({'success': False, 'message': 'Usuario y contraseña son requeridos.'}), 400

    try:
        conn = pyodbc.connect(CONNECTION_STRING)
        cursor = conn.cursor()
        sql = "SELECT COUNT(1) FROM dbo.Users WHERE UserName = ? AND PasswordHash = ?"
        
        cursor.execute(sql, (username, password))
        count = cursor.fetchone()[0]
        conn.close()

        if count == 1:
            # Login exitoso: Redirige a la página de edición
            return jsonify({'success': True, 'redirect': 'edit_skills.html'}), 200
        else:
            return jsonify({'success': False, 'message': 'Credenciales inválidas.'}), 401
    
    except pyodbc.Error as ex:
        return jsonify({'success': False, 'message': f"Error de DB: {str(ex)}"}), 500


# --- 4. ENDPOINTS DE CONFIGURACIÓN (Settings) ---

# ENDPOINT: Leer una configuración por Key (GET /api/settings/<key>)
@app.route('/api/settings/<key>', methods=['GET'])
def get_setting(key):
    try:
        conn = pyodbc.connect(CONNECTION_STRING)
        cursor = conn.cursor()
        sql = "SELECT SettingValue FROM dbo.Settings WHERE SettingKey = ?"
        cursor.execute(sql, (key,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return jsonify({'SettingValue': row[0]}), 200
        else:
            return jsonify({'SettingValue': 'Setting no encontrado.'}), 404
        
    except pyodbc.Error as ex:
        return jsonify({'error': f"Error de DB: {str(ex)}"}), 500


# ENDPOINT: Actualizar una configuración (POST /api/settings/update)
@app.route('/api/settings/update', methods=['POST'])
def update_setting():
    data = request.get_json()
    key = data.get('SettingKey')
    value = data.get('SettingValue')
    
    if not key or not value:
        return jsonify({'success': False, 'message': 'Key y Value son requeridos.'}), 400

    sql = "UPDATE dbo.Settings SET SettingValue = ? WHERE SettingKey = ?"
    
    success, error = execute_db_command(sql, (value, key))
    
    if success:
        return jsonify({'success': True}), 200
    else:
        return jsonify({'success': False, 'message': f"No se pudo actualizar: {error}"}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5029)