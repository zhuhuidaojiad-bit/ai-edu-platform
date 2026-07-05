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
    """AI学习助手 — 调用DeepSeek API实现真正的AI对话"""
    data = request.get_json()
    msg = data.get('message', '').strip()
    nickname = data.get('nickname', '同学')

    # 尝试调用豆包API (火山引擎Ark)
    DOUBAO_KEY = 'ark-b7559c3e-a842-4934-bdc1-6a29f159140d-c2186'
    try:
        import urllib.request, ssl
        req_body = json.dumps({
            'model': 'doubao-seed-2-1-turbo-260628',
            'messages': [
                {'role': 'user', 'content': f'你是AI智慧学伴的AI学习助手，学生叫{nickname}。请用中文回答，语气亲切像学长学姐。回答控制在300字以内，多举具体学科例子。结尾给一个学习建议。'},
                {'role': 'user', 'content': msg}
            ],
            'max_tokens': 1200
        }).encode('utf-8')
        req = urllib.request.Request('https://ark.cn-beijing.volces.com/api/v3/chat/completions',
            data=req_body,
            headers={'Authorization': f'Bearer {DOUBAO_KEY}', 'Content-Type': 'application/json'},
            method='POST')
        ctx = ssl.create_default_context()
        resp = urllib.request.urlopen(req, timeout=60, context=ctx)
        result = json.loads(resp.read())
        reply = result['choices'][0]['message']['content']
        return jsonify({'success': True, 'reply': reply, 'model': 'doubao'})
    except Exception as e:
        import sys, traceback
        print(f'Doubao API error: {e}', file=sys.stderr)
        traceback.print_exc()

    # 本地知识库（DeepSeek不可用时使用）
    topics = {
        '函数': '定义域是函数的基础！先求定义域再做题。单调性看导数正负，奇偶性看f(-x)与f(x)关系。建议：画图帮助理解，多做图像题。',
        '导数': '三步走：①求导 ②找驻点(f\'(x)=0) ③判单调区间。压轴题最爱考导数+不等式。必会：$f\'(x)>0$递增，$f\'(x)<0$递减。',
        '数列': '通项公式+求和公式是核心。等差:$a_n=a_1+(n-1)d$。等比:$a_n=a_1q^{n-1}$。递推数列用累加/累乘/构造法。',
        '三角': '核心公式必须背：$\sin^2+\cos^2=1$，和差公式，二倍角。特殊角30°45°60°的值要脱口而出。',
        '向量': '坐标运算是王道！$\vec{a}\cdot\vec{b}=x_1x_2+y_1y_2$。模长$|\vec{a}|=\sqrt{x^2+y^2}$。夹角$\cos\theta=\frac{\vec{a}\cdot\vec{b}}{|\vec{a}||\vec{b}|}$。',
        '几何': '解析几何万能步骤：设直线→联立→韦达定理→代入条件。椭圆$e<1$，双曲线$e>1$。',
        '概率': '分步用乘法，分类用加法。超几何分布和二项分布最容易混淆！注意"有放回"vs"无放回"。',
        '力学': '受力分析三步：①画对象 ②标力 ③建坐标。$F=ma$是核心，动能定理和动量守恒是两大法宝。',
        '电磁': '电磁感应：$E=BLv$（动生），$E=n\\frac{\\Delta\\Phi}{\\Delta t}$（感生）。楞次定律：增反减同，来拒去留。',
        '化学': '氧化还原：升失氧，降得还。化学平衡：勒夏特列原理。离子方程式：拆强不拆弱，拆溶不拆沉。',
        '英语': '阅读理解先看题目再读文章！完形填空找上下文线索。作文套模板+高级词汇=高分。',
    }

    for keyword, answer in topics.items():
        if keyword in msg:
            return jsonify({'success': True, 'reply': f'📚 **{keyword}**\n\n{answer}'})

    if '错题' in msg:
        return jsonify({'success': True, 'reply': f'{nickname}，分析错题三步：\n1️⃣ 判断错误类型（概念/计算/审题）\n2️⃣ 重做一遍不看答案\n3️⃣ 找同类题练3道\n\n建议每天固定时间复习错题本！'})
    if '高考' in msg or '倒计时' in msg:
        from datetime import date
        days = (date(2027, 6, 7) - date.today()).days
        return jsonify({'success': True, 'reply': f'⏳ 距2027高考还有**{days}天**！\n\n💪 {nickname}，现在开始努力，一切来得及！每天做10道真题，坚持就是胜利！'})

    return jsonify({'success': True, 'reply': f'{nickname}你好！我可以帮你：\n📖 讲解知识点（输入"函数""导数""数列"等）\n🔍 分析错题（输入"错题"）\n⏳ 高考倒计时（输入"高考"）\n💡 推荐学习方法\n\n试试输入一个知识点吧！'})

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
