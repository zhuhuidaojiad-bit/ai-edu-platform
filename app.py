"""
AI 智慧学伴 — PythonAnywhere 部署版
使用 Flask + SQLite，完全免费
"""
import os, json, uuid, sqlite3
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder='.', static_url_path='')
DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'edu.db')

def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS access_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE NOT NULL,
            duration_minutes INTEGER NOT NULL, max_activations INTEGER DEFAULT 1,
            activation_count INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nickname TEXT NOT NULL,
            phone TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            code_id INTEGER NOT NULL, session_token TEXT UNIQUE NOT NULL,
            activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, expires_at TIMESTAMP NOT NULL,
            remaining_seconds INTEGER NOT NULL, is_active INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (code_id) REFERENCES access_codes(id)
        );
    ''')
    existing = conn.execute("SELECT COUNT(*) FROM access_codes").fetchone()[0]
    if existing == 0:
        codes = [
            ('TEST-1H-001', 60, 100), ('TEST-2H-001', 120, 50),
            ('TEST-4H-001', 240, 30), ('STUDENT-DAY', 1440, 500),
            ('STUDENT-WEEK', 10080, 100), ('FREE-TRIAL', 30, 1000),
        ]
        for code, mins, max_act in codes:
            conn.execute("INSERT INTO access_codes (code, duration_minutes, max_activations) VALUES (?, ?, ?)",
                         (code, mins, max_act))
    conn.commit()
    conn.close()

init_db()

# ── Routes ──
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('.', path)

@app.route('/api/validate_code', methods=['POST'])
def api_validate_code():
    data = request.get_json()
    code = data.get('code', '').strip().upper()
    nickname = data.get('nickname', '').strip()
    if not code or not nickname:
        return jsonify({'success': False, 'error': '请输入访问码和昵称'})

    conn = get_db()
    row = conn.execute("SELECT * FROM access_codes WHERE code=? AND is_active=1", (code,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'success': False, 'error': '访问码无效'})
    if row['activation_count'] >= row['max_activations']:
        conn.close()
        return jsonify({'success': False, 'error': '该访问码已达最大使用次数'})

    user = conn.execute("SELECT * FROM users WHERE nickname=?", (nickname,)).fetchone()
    if not user:
        conn.execute("INSERT INTO users (nickname) VALUES (?)", (nickname,))
        user = conn.execute("SELECT * FROM users WHERE nickname=?", (nickname,)).fetchone()

    active_session = conn.execute(
        "SELECT * FROM sessions WHERE user_id=? AND is_active=1 AND expires_at > datetime('now') ORDER BY expires_at DESC LIMIT 1",
        (user['id'],)).fetchone()

    now = datetime.now()
    if active_session:
        current_expires = datetime.fromisoformat(active_session['expires_at'])
        if current_expires < now: current_expires = now
        new_expires = current_expires + timedelta(minutes=row['duration_minutes'])
        new_remaining = int((new_expires - now).total_seconds())
    else:
        new_expires = now + timedelta(minutes=row['duration_minutes'])
        new_remaining = row['duration_minutes'] * 60

    session_token = str(uuid.uuid4())
    conn.execute("INSERT INTO sessions (user_id, code_id, session_token, expires_at, remaining_seconds) VALUES (?, ?, ?, ?, ?)",
                 (user['id'], row['id'], session_token, new_expires.isoformat(), new_remaining))
    if active_session:
        conn.execute("UPDATE sessions SET is_active=0 WHERE id=?", (active_session['id'],))
    conn.execute("UPDATE access_codes SET activation_count = activation_count + 1 WHERE id=?", (row['id'],))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'session_token': session_token, 'nickname': nickname,
                    'duration_minutes': row['duration_minutes'], 'total_remaining_seconds': new_remaining,
                    'expires_at': new_expires.isoformat(),
                    'message': f"✅ 访问码验证成功！已{'叠加' if active_session else '激活'}{row['duration_minutes']}分钟"})

@app.route('/api/check_session', methods=['POST'])
def api_check_session():
    data = request.get_json()
    token = data.get('session_token', '').strip()
    if not token:
        return jsonify({'success': False, 'error': '未登录'})
    conn = get_db()
    session = conn.execute(
        "SELECT s.*, u.nickname FROM sessions s JOIN users u ON s.user_id=u.id WHERE s.session_token=? AND s.is_active=1",
        (token,)).fetchone()
    if not session:
        conn.close()
        return jsonify({'success': False, 'error': '会话无效'})
    now = datetime.now()
    expires_at = datetime.fromisoformat(session['expires_at'])
    remaining = max(0, int((expires_at - now).total_seconds()))
    conn.execute("UPDATE sessions SET remaining_seconds=? WHERE id=?", (remaining, session['id']))
    if remaining <= 0:
        conn.execute("UPDATE sessions SET is_active=0 WHERE id=?", (session['id'],))
        conn.commit(); conn.close()
        return jsonify({'success': False, 'error': '学习时间已用完', 'expired': True})
    conn.commit(); conn.close()
    h, m = remaining // 3600, (remaining % 3600) // 60
    return jsonify({'success': True, 'nickname': session['nickname'], 'remaining_seconds': remaining,
                    'remaining_display': f"{h}小时{m}分钟" if h > 0 else f"{m}分钟",
                    'expires_at': session['expires_at']})

@app.route('/api/heartbeat', methods=['POST'])
def api_heartbeat():
    return api_check_session()

@app.route('/api/generate_codes', methods=['POST'])
def api_generate_codes():
    data = request.get_json()
    if data.get('admin_key', '') != 'admin2024edu':
        return jsonify({'success': False, 'error': '管理员密钥错误'})
    duration = data.get('duration_minutes', 60)
    count = data.get('count', 10)
    prefix = data.get('prefix', 'EDU')
    conn = get_db()
    codes = []
    for i in range(count):
        code = f"{prefix}-{uuid.uuid4().hex[:6].upper()}"
        conn.execute("INSERT INTO access_codes (code, duration_minutes, max_activations) VALUES (?, ?, 1)", (code, duration))
        codes.append({'code': code, 'duration_minutes': duration})
    conn.commit(); conn.close()
    return jsonify({'success': True, 'codes': codes, 'count': len(codes)})

@app.route('/api/stats')
def api_stats():
    conn = get_db()
    total_codes = conn.execute("SELECT COUNT(*) FROM access_codes").fetchone()[0]
    active_codes = conn.execute("SELECT COUNT(*) FROM access_codes WHERE is_active=1 AND activation_count < max_activations").fetchone()[0]
    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    active_sessions = conn.execute("SELECT COUNT(*) FROM sessions WHERE is_active=1 AND expires_at > datetime('now')").fetchone()[0]
    conn.close()
    return jsonify({'success': True, 'stats': {'total_codes': total_codes, 'active_codes': active_codes,
                                                'total_users': total_users, 'active_sessions': active_sessions}})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=False)
