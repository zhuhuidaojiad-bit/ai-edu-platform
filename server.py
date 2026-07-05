#!/usr/bin/env python3
"""
AI 智慧学伴 — 后端服务器
纯 Python 标准库实现：HTTP API + SQLite 数据库
管理访问码、用户会话、使用记录
"""
import http.server
import json
import sqlite3
import os
import time
import uuid
import hashlib
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'edu.db')
WWW_DIR = os.path.dirname(__file__)

# ═══════════════════════════════════
# DATABASE
# ═══════════════════════════════════
def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS access_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            duration_minutes INTEGER NOT NULL,
            max_activations INTEGER DEFAULT 1,
            activation_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nickname TEXT NOT NULL,
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            code_id INTEGER NOT NULL,
            session_token TEXT UNIQUE NOT NULL,
            activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            remaining_seconds INTEGER NOT NULL,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (code_id) REFERENCES access_codes(id)
        );
    ''')
    # 插入默认测试码（如果不存在）
    existing = conn.execute("SELECT COUNT(*) FROM access_codes").fetchone()[0]
    if existing == 0:
        test_codes = [
            ('TEST-1H-001', 60, 100),
            ('TEST-2H-001', 120, 50),
            ('TEST-4H-001', 240, 30),
            ('TEST-8H-001', 480, 20),
            ('TEST-24H-001', 1440, 10),
            ('STUDENT-DAY', 1440, 500),
            ('STUDENT-WEEK', 10080, 100),
        ]
        for code, mins, max_act in test_codes:
            conn.execute(
                "INSERT INTO access_codes (code, duration_minutes, max_activations) VALUES (?, ?, ?)",
                (code, mins, max_act)
            )
    conn.commit()
    conn.close()

# ═══════════════════════════════════
# API HANDLERS
# ═══════════════════════════════════
def api_validate_code(data):
    """验证访问码"""
    code = data.get('code', '').strip().upper()
    nickname = data.get('nickname', '').strip()

    if not code or not nickname:
        return {'success': False, 'error': '请输入访问码和昵称'}

    conn = get_db()
    row = conn.execute(
        "SELECT * FROM access_codes WHERE code=? AND is_active=1", (code,)
    ).fetchone()

    if not row:
        conn.close()
        return {'success': False, 'error': '访问码无效'}

    if row['activation_count'] >= row['max_activations']:
        conn.close()
        return {'success': False, 'error': '该访问码已达到最大使用次数'}

    # 查找或创建用户
    user = conn.execute("SELECT * FROM users WHERE nickname=?", (nickname,)).fetchone()
    if not user:
        conn.execute("INSERT INTO users (nickname) VALUES (?)", (nickname,))
        user = conn.execute("SELECT * FROM users WHERE nickname=?", (nickname,)).fetchone()

    # 检查是否有活跃会话（可叠加时间）
    active_session = conn.execute(
        "SELECT * FROM sessions WHERE user_id=? AND is_active=1 AND expires_at > datetime('now') ORDER BY expires_at DESC LIMIT 1",
        (user['id'],)
    ).fetchone()

    # 计算新过期时间
    now = datetime.now()
    if active_session:
        # 叠加：在现有过期时间上增加
        current_expires = datetime.fromisoformat(active_session['expires_at'])
        if current_expires < now:
            current_expires = now
        new_expires = current_expires + timedelta(minutes=row['duration_minutes'])
        new_remaining = int((new_expires - now).total_seconds())
    else:
        new_expires = now + timedelta(minutes=row['duration_minutes'])
        new_remaining = row['duration_minutes'] * 60

    # 创建会话
    session_token = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO sessions (user_id, code_id, session_token, expires_at, remaining_seconds) VALUES (?, ?, ?, ?, ?)",
        (user['id'], row['id'], session_token, new_expires.isoformat(), new_remaining)
    )
    # 停用旧会话
    if active_session:
        conn.execute("UPDATE sessions SET is_active=0 WHERE id=?", (active_session['id'],))

    # 增加激活计数
    conn.execute(
        "UPDATE access_codes SET activation_count = activation_count + 1 WHERE id=?",
        (row['id'],)
    )

    conn.commit()
    conn.close()

    return {
        'success': True,
        'session_token': session_token,
        'nickname': nickname,
        'duration_minutes': row['duration_minutes'],
        'total_remaining_seconds': new_remaining,
        'expires_at': new_expires.isoformat(),
        'message': f"✅ 访问码验证成功！已{'叠加' if active_session else '激活'}{row['duration_minutes']}分钟学习时间"
    }

def api_check_session(data):
    """检查会话状态"""
    token = data.get('session_token', '').strip()
    if not token:
        return {'success': False, 'error': '未登录'}

    conn = get_db()
    session = conn.execute(
        "SELECT s.*, u.nickname FROM sessions s JOIN users u ON s.user_id=u.id WHERE s.session_token=? AND s.is_active=1",
        (token,)
    ).fetchone()

    if not session:
        conn.close()
        return {'success': False, 'error': '会话无效，请重新输入访问码'}

    now = datetime.now()
    expires_at = datetime.fromisoformat(session['expires_at'])
    remaining = max(0, int((expires_at - now).total_seconds()))

    # 更新剩余时间
    conn.execute("UPDATE sessions SET remaining_seconds=? WHERE id=?", (remaining, session['id']))

    if remaining <= 0:
        conn.execute("UPDATE sessions SET is_active=0 WHERE id=?", (session['id'],))
        conn.commit()
        conn.close()
        return {'success': False, 'error': '学习时间已用完，请输入新访问码', 'expired': True}

    conn.commit()
    conn.close()

    hours = remaining // 3600
    minutes = (remaining % 3600) // 60
    time_str = f"{hours}小时{minutes}分钟" if hours > 0 else f"{minutes}分钟"

    return {
        'success': True,
        'nickname': session['nickname'],
        'remaining_seconds': remaining,
        'remaining_display': time_str,
        'expires_at': session['expires_at']
    }

def api_heartbeat(data):
    """心跳——前端定期调用以更新剩余时间"""
    return api_check_session(data)

def api_generate_codes(data):
    """管理员生成批量码"""
    admin_key = data.get('admin_key', '')
    if admin_key != 'admin2024edu':
        return {'success': False, 'error': '管理员密钥错误'}

    duration = data.get('duration_minutes', 60)
    count = data.get('count', 10)
    prefix = data.get('prefix', 'EDU')

    conn = get_db()
    codes = []
    for i in range(count):
        code = f"{prefix}-{uuid.uuid4().hex[:6].upper()}"
        conn.execute(
            "INSERT INTO access_codes (code, duration_minutes, max_activations) VALUES (?, ?, 1)",
            (code, duration)
        )
        codes.append({'code': code, 'duration_minutes': duration})

    conn.commit()
    conn.close()
    return {'success': True, 'codes': codes, 'count': len(codes)}

def api_stats():
    """管理员统计"""
    conn = get_db()
    total_codes = conn.execute("SELECT COUNT(*) FROM access_codes").fetchone()[0]
    active_codes = conn.execute("SELECT COUNT(*) FROM access_codes WHERE is_active=1 AND activation_count < max_activations").fetchone()[0]
    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    active_sessions = conn.execute("SELECT COUNT(*) FROM sessions WHERE is_active=1 AND expires_at > datetime('now')").fetchone()[0]
    conn.close()
    return {
        'success': True,
        'stats': {
            'total_codes': total_codes,
            'active_codes': active_codes,
            'total_users': total_users,
            'active_sessions': active_sessions
        }
    }

# ═══════════════════════════════════
# HTTP SERVER
# ═══════════════════════════════════
API_ROUTES = {
    '/api/validate_code': api_validate_code,
    '/api/check_session': api_check_session,
    '/api/heartbeat': api_heartbeat,
    '/api/generate_codes': api_generate_codes,
    '/api/stats': api_stats,
}

class EduServer(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WWW_DIR, **kwargs)

    def do_POST(self):
        path = urlparse(self.path).path
        if path in API_ROUTES:
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length) if content_length else b'{}'
                data = json.loads(body)
                result = API_ROUTES[path](data)
                self._send_json(result)
            except Exception as e:
                self._send_json({'success': False, 'error': str(e)}, 500)
        else:
            self._send_json({'success': False, 'error': 'Not found'}, 404)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/api/stats':
            self._send_json(api_stats())
        else:
            super().do_GET()

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        # 简洁日志
        if '/api/' in str(args[0]):
            print(f"[API] {args[0]}")
        else:
            pass  # 不记录静态文件请求

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5050))
    print(f"""
╔══════════════════════════════════════╗
║   🎓 AI 智慧学伴 — 后端服务已启动   ║
║   地址: http://localhost:{port}        ║
║   数据库: {DB_PATH}
║   API 端点: /api/validate_code       ║
║            /api/check_session        ║
║            /api/heartbeat            ║
║            /api/generate_codes       ║
║            /api/stats                ║
║   测试码: TEST-1H-001 (1小时)        ║
║          TEST-2H-001 (2小时)         ║
║          STUDENT-DAY (24小时)        ║
╚══════════════════════════════════════╝
""")
    http.server.HTTPServer(('0.0.0.0', port), EduServer).serve_forever()
