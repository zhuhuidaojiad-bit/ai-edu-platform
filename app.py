"""
AI 智慧学伴 — PythonAnywhere 部署版
使用 Flask + SQLite，完全免费
"""
import os, json, uuid, sqlite3
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=BASE_DIR, static_url_path='')
DB_PATH = os.path.join(BASE_DIR, 'data', 'edu.db')

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
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/<path:path>')
def static_files(path):
    if path.startswith('api/'):
        return jsonify({'success': False, 'error': 'Not found'}), 404
    return send_from_directory(BASE_DIR, path)

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

@app.route('/api/chat', methods=['POST'])
def api_chat():
    """AI学习助手 — 搜索题库 + 知识点解答"""
    data = request.get_json()
    msg = data.get('message', '').strip()
    nickname = data.get('nickname', '同学')

    # 关键词匹配题库
    reply = ''
    topics = {
        '函数': '函数是高中数学核心。定义域、值域、单调性、奇偶性是基础。建议从集合映射开始理解，多做图像题。',
        '导数': '导数是高考压轴热点！记住公式：$(x^n)\'=nx^{n-1}$，$(e^x)\'=e^x$，$(\\ln x)\'=1/x$。导数应用：求切线、判断单调性、求极值最值。',
        '数列': '等差 $a_n=a_1+(n-1)d$，等比 $a_n=a_1q^{n-1}$。求和公式要烂熟于心。递推数列用累加/累乘法。',
        '三角': '核心公式：$\\sin^2\\alpha+\\cos^2\\alpha=1$，和差公式，倍角公式。记住特殊角(30°,45°,60°)的三角函数值。',
        '向量': '$\\vec{a}\\cdot\\vec{b}=|\\vec{a}||\\vec{b}|\\cos\\theta$。坐标运算：$\\vec{a}\\cdot\\vec{b}=x_1x_2+y_1y_2$。',
        '概率': '古典概型：$P=\\frac{有利}{总}$。二项分布、正态分布是考点。注意区分互斥事件和独立事件。',
        '几何': '解析几何：联立方程+韦达定理。椭圆$e=c/a<1$，双曲线$e=c/a>1$。焦点、准线要分清。',
        '力学': '牛顿第二定律 $F=ma$。受力分析先画图。动能定理和动量守恒是解题利器。',
        '电磁': '左手定则判力，右手定则判感生。$F=BIL$，$E=BLv$。楞次定律：增反减同。',
        '化学': '氧化剂得电子降价，还原剂失电子升价。化学平衡：勒夏特列原理。pH计算：$pH=-\\lg[H^+]$。',
        '方程': '解方程核心思路：去分母→去括号→移项→合并同类项→系数化1。分式方程记得检验增根。',
        '圆': '圆的标准方程 $(x-a)^2+(y-b)^2=r^2$。切线性质：圆心到切线距离=半径。弦长公式$2\\sqrt{r^2-d^2}$。',
    }

    matched = False
    for keyword, answer in topics.items():
        if keyword in msg:
            reply = f'📚 **{keyword}**\n\n{answer}'
            matched = True
            break

    if not matched:
        if '错题' in msg or '错因' in msg:
            reply = f'🔍 {nickname}，分析错因很重要！\n\n常见错误类型：\n📊 概念混淆（35%）\n📊 计算失误（25%）\n📊 审题不清（20%）\n📊 方法不当（20%）\n\n建议：每天复习3-5道错题，重复练习直到掌握！'
        elif '推荐' in msg or '练习' in msg:
            reply = f'💡 {nickname}，基于你的学习情况：\n\n🎯 先复习错题本\n🎯 从薄弱科目开始\n🎯 每天坚持10-15题\n\n告诉我你想练哪个科目？'
        elif '高考' in msg or '倒计时' in msg:
            from datetime import date
            gk = date(2027, 6, 7)
            days = (gk - date.today()).days
            reply = f'⏳ 距2027年高考还有 **{days}** 天！\n\n💪 每天进步一点点，坚持就是胜利！'
        else:
            reply = f'👋 {nickname}，我是你的AI学习助手！\n\n我可以帮你：\n📖 讲解知识点（函数/导数/数列/三角/向量/概率/几何）\n🔍 分析错题原因\n💡 推荐练习题\n⚡ 解答物理/化学问题\n\n直接问我具体知识点吧！'

    return jsonify({'success': True, 'reply': reply})

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

@app.after_request
def add_no_cache(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/api/ocr', methods=['POST'])
def api_ocr():
    """OCR 图片识别 — 提取图片中的文字"""
    import base64, tempfile
    data = request.get_json()
    img_b64 = data.get('image', '')
    if not img_b64 or len(img_b64) < 100:
        return jsonify({'success': False, 'error': '图片数据为空'})

    # 去掉 data:image/...;base64, 前缀
    if ',' in img_b64:
        img_b64 = img_b64.split(',', 1)[1]

    try:
        img_bytes = base64.b64decode(img_b64)
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            f.write(img_bytes)
            tmp_path = f.name

        # 尝试使用 easyocr
        try:
            import easyocr
            reader = easyocr.Reader(['ch_sim', 'en'], gpu=False, verbose=False)
            result = reader.readtext(tmp_path)
            texts = [item[1] for item in result if item[2] > 0.3]
            os.unlink(tmp_path)
            if texts:
                return jsonify({'success': True, 'text': '\\n'.join(texts), 'method': 'easyocr'})
        except Exception as e:
            pass

        # 尝试使用 pytesseract
        try:
            from PIL import Image
            import pytesseract
            img = Image.open(tmp_path)
            text = pytesseract.image_to_string(img, lang='chi_sim+eng')
            os.unlink(tmp_path)
            if text and text.strip():
                return jsonify({'success': True, 'text': text.strip(), 'method': 'tesseract'})
        except:
            pass

        # Fallback: 返回图片已接收
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        return jsonify({'success': True, 'text': '[图片已接收，请手动输入答案]', 'method': 'none'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5052, debug=False)
