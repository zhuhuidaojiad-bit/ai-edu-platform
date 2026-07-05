#!/usr/bin/env python3
"""
DeepSeek API 题目生成器 — 批量生成各年级真实考题

使用方法：
  # 设置API Key
  export DEEPSEEK_API_KEY="sk-your-key-here"

  # 生成初中数学20道选择题
  python3 generate_questions.py --grade 初中 --subject math --count 20 --type 选择题

  # 生成高一物理10道填空题
  python3 generate_questions.py --grade 高一 --subject phys --count 10 --type 填空题

  # 批量生成所有年级所有科目
  python3 generate_questions.py --all

  # 替换网站demo数据
  python3 generate_questions.py --all --replace

输出格式与网站data.js完全兼容，生成后自动合并。
"""

import json
import os
import sys
import time
import argparse
import re

# ═══════════════════════════════════════════
# 知识点图谱 — 确保生成的题目覆盖真实考纲
# ═══════════════════════════════════════════

CURRICULUM = {
    '初中': {
        'math': [
            '有理数混合运算', '整式加减乘除', '一元一次方程', '二元一次方程组',
            '不等式与不等式组', '平面直角坐标系', '一次函数', '反比例函数',
            '二次函数', '三角形全等', '勾股定理', '平行四边形', '圆的性质',
            '相似三角形', '锐角三角函数', '统计与概率',
        ],
        'phys': [
            '机械运动', '声现象', '物态变化', '光的反射折射',
            '透镜成像', '质量与密度', '力与运动', '压强',
            '浮力', '简单机械', '功和功率', '内能',
            '电路与电流', '电压电阻', '欧姆定律', '电功率',
        ],
        'chem': [
            '物质变化', '空气组成', '氧气制取', '水的组成',
            '化学方程式', '碳及其化合物', '金属材料', '溶液',
            '酸碱盐', '化学肥料',
        ],
        'bio': [
            '细胞结构', '光合作用', '呼吸作用', '遗传与变异',
            '人体系统', '免疫', '生态系统',
        ],
        'engl': [
            '名词代词', '动词时态', '被动语态', '形容词副词',
            '介词连词', '宾语从句', '状语从句', '完形填空',
            '阅读理解', '书面表达',
        ],
        'chin': [
            '字音字形', '成语运用', '病句修改', '文言文阅读',
            '古诗词鉴赏', '现代文阅读', '作文',
        ],
        'hist': [
            '中国古代史', '中国近代史', '世界古代史', '世界近代史',
        ],
        'geo': [
            '地球与地图', '中国地理', '世界地理', '气候类型',
        ],
        'poli': [
            '道德与法治', '宪法', '权利义务', '基本制度',
            '国家机构', '经济制度', '文化传承',
        ],
    },
    '高一': {
        'math': [
            '集合与逻辑', '函数概念', '指数函数', '对数函数',
            '三角函数', '平面向量', '数列基础', '不等式',
        ],
        'phys': [
            '运动的描述', '匀变速直线运动', '相互作用', '牛顿运动定律',
            '曲线运动', '万有引力', '机械能守恒',
        ],
        'chem': [
            '物质的量', '离子反应', '氧化还原', '金属钠',
            '氯气', '硫及其化合物', '氮及其化合物', '元素周期律',
        ],
        'bio': [
            '细胞结构', '细胞代谢', '光合作用', '细胞呼吸',
            '细胞分裂', '遗传因子', 'DNA结构',
        ],
        'engl': [
            '定语从句', '名词性从句', '非谓语动词', '虚拟语气',
            '倒装句', '阅读理解', '完形填空', '写作',
        ],
        'chin': [
            '文言文阅读', '古代诗歌', '现代文阅读', '语言运用',
            '作文',
        ],
        'hist': [
            '中国古代政治', '列强侵华', '近代探索', '中共党史',
        ],
        'geo': [
            '地球运动', '大气环流', '洋流', '人口与城市',
        ],
        'poli': [
            '经济生活', '政治生活', '文化生活', '哲学常识',
        ],
    },
    '高二': {
        'math': [
            '导数', '定积分', '排列组合', '概率分布',
            '空间向量', '圆锥曲线', '数列极限',
        ],
        'phys': [
            '电场', '恒定电流', '磁场', '电磁感应',
            '交变电流', '热力学', '机械振动', '光学',
        ],
        'chem': [
            '有机化学', '化学平衡', '电离平衡', '电化学',
            '物质结构', '配合物',
        ],
        'bio': [
            '遗传定律', '变异与育种', '进化', '内环境稳态',
            '神经调节', '体液调节', '免疫调节', '生态',
        ],
        'engl': [
            '高级语法', '长难句分析', '完形填空', '阅读理解',
            '七选五', '短文改错', '写作',
        ],
        'chin': [
            '文言文阅读', '古诗鉴赏', '散文阅读', '小说阅读',
            '作文',
        ],
        'hist': [
            '古代政治制度', '近代民主革命', '现代中国', '世界格局',
        ],
        'geo': [
            '区域地理', '产业转移', '资源调配', '可持续发展',
        ],
        'poli': [
            '经济生活', '政治生活', '文化生活', '哲学生活',
        ],
    },
}

# ═══════════════════════════════════════════
# 内置题库 — 基于考纲手编（比纯demo强）
# ═══════════════════════════════════════════

def generate_builtin(grade, subject, count=15):
    """基于知识点图谱生成结构化题目（不依赖API）"""
    topics = CURRICULUM.get(grade, {}).get(subject, ['综合'])
    questions = []
    qid = 0

    for i in range(min(count, len(topics) * 2)):
        topic = topics[i % len(topics)]
        qid += 1

        # 根据科目和知识点构造题目
        q = make_question(grade, subject, topic, i)
        if q:
            q['id'] = f'b{grade[0]}{subject[0]}{qid}'
            q['topic'] = topic
            q['source'] = f'考纲知识点·{topic}'
            questions.append(q)

    return questions


def make_question(grade, subject, topic, idx):
    """基于知识点构造一道题"""
    base = {
        'year': 2024, 'grade': grade, 'subject': subject,
        'type': '选择题', 'difficulty': 2,
        'options': [],
    }

    # 数学模板
    if subject == 'math':
        if '一元一次方程' in topic:
            base['question'] = '方程 2x + 3 = 7 的解是（  ）'
            base['options'] = ['A. x=1', 'B. x=2', 'C. x=3', 'D. x=4']
            base['answer'] = 'B'
            base['explanation'] = '2x+3=7 → 2x=4 → x=2'
            base['steps'] = ['移项：2x=7-3', '计算：2x=4', '系数化1：x=2']
        elif '勾股定理' in topic:
            base['question'] = '直角三角形的两条直角边分别为3和4，则斜边长为（  ）'
            base['options'] = ['A. 4', 'B. 5', 'C. 6', 'D. 7']
            base['answer'] = 'B'
            base['explanation'] = 'c²=3²+4²=25，c=5'
            base['steps'] = ['勾股定理：c²=a²+b²', 'c²=9+16=25', 'c=5']
        elif '二次函数' in topic and grade == '初中':
            base['question'] = '抛物线 y=x²-4x+3 的顶点坐标是（  ）'
            base['options'] = ['A. (2,-1)', 'B. (-2,-1)', 'C. (2,1)', 'D. (-2,1)']
            base['answer'] = 'A'
            base['explanation'] = 'y=(x-2)²-1，顶点(2,-1)'
            base['steps'] = ['配方：y=(x²-4x+4)-1', 'y=(x-2)²-1', '顶点(2,-1)']
        elif '集合' in topic:
            base['question'] = '已知集合A={1,2,3}，B={2,3,4}，则A∩B=（  ）'
            base['options'] = ['A. {1}', 'B. {2,3}', 'C. {1,2,3,4}', 'D. {4}']
            base['answer'] = 'B'
            base['explanation'] = 'A∩B是A和B的公共元素组成的集合，即{2,3}'
            base['steps'] = ['A={1,2,3}, B={2,3,4}', '公共元素：2和3', 'A∩B={2,3}']
        elif '三角函数' in topic and grade == '高一':
            base['question'] = 'sin30°+cos60°的值为（  ）'
            base['options'] = ['A. 0', 'B. 0.5', 'C. 1', 'D. 1.5']
            base['answer'] = 'C'
            base['explanation'] = 'sin30°=1/2，cos60°=1/2，和为1'
            base['steps'] = ['sin30°=1/2', 'cos60°=1/2', '和=1']
        elif '导数' in topic:
            base['question'] = '函数f(x)=x³-3x的单调递增区间是（  ）'
            base['options'] = ['A. (-∞,-1)∪(1,+∞)', 'B. (-1,1)', 'C. (-∞,0)', 'D. (0,+∞)']
            base['answer'] = 'A'
            base['explanation'] = 'f\'(x)=3x²-3=3(x+1)(x-1)，f\'(x)>0得x<-1或x>1'
            base['steps'] = ['求导：f\'(x)=3x²-3', '令f\'(x)>0：3(x+1)(x-1)>0', '解得x<-1或x>1']
        else:
            # Varied templates based on topic keyword
            templates = [
                {'q': f'（{topic}）下列计算正确的是（  ）', 'opts': ['A. (-2)²=-4', 'B. |-3|=-3', 'C. √16=4', 'D. 2³=6'], 'ans': 'C', 'exp': '(-2)²=4≠-4；|-3|=3≠-3；√16=4✓；2³=8≠6'},
                {'q': f'（{topic}）若a=2，b=-1，则a²-b²的值为（  ）', 'opts': ['A. 1', 'B. 3', 'C. 5', 'D. 7'], 'ans': 'B', 'exp': 'a²-b²=4-1=3'},
                {'q': f'（{topic}）下列各数中最大的是（  ）', 'opts': ['A. |-5|', 'B. -(-3)', 'C. 0', 'D. -2'], 'ans': 'A', 'exp': '|-5|=5, -(-3)=3, 5>3>0>-2'},
                {'q': f'（{topic}）已知x=-1是方程2x+k=0的解，则k=（  ）', 'opts': ['A. -2', 'B. -1', 'C. 1', 'D. 2'], 'ans': 'D', 'exp': '代入x=-1：-2+k=0，k=2'},
            ]
            t = templates[idx % len(templates)]
            base['question'] = t['q']
            base['options'] = t['opts']
            base['answer'] = t['ans']
            base['explanation'] = t['exp']
            base['steps'] = ['分析题意', '运用相关知识点', t['exp']]

    # 物理模板
    elif subject == 'phys':
        if '压强' in topic:
            base['question'] = '下列实例中增大压强的是（  ）'
            base['options'] = ['A. 书包带宽', 'B. 刀刃磨薄', 'C. 铁轨铺枕木', 'D. 坦克宽履带']
            base['answer'] = 'B'
            base['explanation'] = 'P=F/S，刀刃薄→S小→P大'
            base['steps'] = ['压强公式P=F/S', '减小受力面积增大压强', '刀刃薄=面积小=压强大']
        elif '欧姆定律' in topic:
            base['question'] = '电阻两端电压12V，电流0.5A，则电阻值为（  ）'
            base['options'] = ['A. 6Ω', 'B. 12Ω', 'C. 18Ω', 'D. 24Ω']
            base['answer'] = 'D'
            base['explanation'] = 'R=U/I=12/0.5=24Ω'
            base['steps'] = ['欧姆定律：R=U/I', 'R=12/0.5=24Ω']
        elif '牛顿' in topic:
            base['question'] = '质量为2kg的物体受10N合外力，加速度为（  ）'
            base['options'] = ['A. 2m/s²', 'B. 5m/s²', 'C. 10m/s²', 'D. 20m/s²']
            base['answer'] = 'B'
            base['explanation'] = 'F=ma，a=F/m=10/2=5m/s²'
            base['steps'] = ['牛顿第二定律：F=ma', 'a=F/m=10N/2kg', 'a=5m/s²']
        elif '电磁感应' in topic:
            base['question'] = '闭合电路中感应电流的方向由（  ）判断'
            base['options'] = ['A. 左手定则', 'B. 右手定则', 'C. 楞次定律', 'D. 安培定则']
            base['answer'] = 'C'
            base['explanation'] = '楞次定律：感应电流的磁场总是阻碍引起感应电流的磁通量变化'
            base['steps'] = ['感应电流方向的判断', '楞次定律：增反减同', '右手定则：切割磁感线时']
        else:
            templates = [
                {'q': f'（{topic}）在国际单位制中，力的单位是（  ）', 'opts': ['A. 千克', 'B. 米', 'C. 牛顿', 'D. 秒'], 'ans': 'C', 'exp': '力的国际单位是牛顿(N)'},
                {'q': f'（{topic}）关于惯性，下列说法正确的是（  ）', 'opts': ['A. 速度大惯性大', 'B. 质量大惯性大', 'C. 静止物体无惯性', 'D. 运动物体无惯性'], 'ans': 'B', 'exp': '惯性只与质量有关，质量越大惯性越大'},
                {'q': f'（{topic}）下列属于省力杠杆的是（  ）', 'opts': ['A. 筷子', 'B. 镊子', 'C. 瓶起子', 'D. 钓鱼竿'], 'ans': 'C', 'exp': '瓶起子动力臂>阻力臂，省力杠杆'},
            ]
            t = templates[idx % len(templates)]
            base['question'] = t['q']
            base['options'] = t['opts']
            base['answer'] = t['ans']
            base['explanation'] = t['exp']
            base['steps'] = ['分析题意', '运用物理概念', t['exp']]

    # 化学模板
    elif subject == 'chem':
        if '化学方程式' in topic:
            base['question'] = '电解水生成H₂和O₂的体积比为（  ）'
            base['options'] = ['A. 1:1', 'B. 2:1', 'C. 1:2', 'D. 3:1']
            base['answer'] = 'B'
            base['explanation'] = '2H₂O→2H₂↑+O₂↑，体积比H₂:O₂=2:1'
            base['steps'] = ['电解水方程：2H₂O→2H₂↑+O₂↑', '分子数比H₂:O₂=2:1', '同条件体积比=分子数比']
        elif '酸碱盐' in topic:
            base['question'] = '下列物质中属于碱的是（  ）'
            base['options'] = ['A. NaCl', 'B. H₂SO₄', 'C. NaOH', 'D. CO₂']
            base['answer'] = 'C'
            base['explanation'] = '碱：阴离子全是OH⁻。NaOH=Na⁺+OH⁻'
            base['steps'] = ['碱的定义', 'NaOH→Na⁺+OH⁻✓', 'NaCl→盐，H₂SO₄→酸']
        else:
            templates = [
                {'q': f'（{topic}）地壳中含量最多的金属元素是（  ）', 'opts': ['A. Fe', 'B. Al', 'C. Ca', 'D. Na'], 'ans': 'B', 'exp': '铝(Al)是地壳中含量最多的金属元素'},
                {'q': f'（{topic}）下列物质属于纯净物的是（  ）', 'opts': ['A. 空气', 'B. 食盐水', 'C. 蒸馏水', 'D. 石油'], 'ans': 'C', 'exp': '蒸馏水只有H₂O，是纯净物'},
                {'q': f'（{topic}）原子核由什么组成（  ）', 'opts': ['A. 电子和质子', 'B. 质子和中子', 'C. 电子和中子', 'D. 质子和电子'], 'ans': 'B', 'exp': '原子核由质子和中子组成，电子在核外'},
            ]
            t = templates[idx % len(templates)]
            base['question'] = t['q']
            base['options'] = t['opts']
            base['answer'] = t['ans']
            base['explanation'] = t['exp']
            base['steps'] = ['回顾相关化学知识', t['exp']]

    # 英语模板
    elif subject == 'engl':
        if '时态' in topic:
            base['question'] = 'She ______ English since she was five years old.'
            base['options'] = ['A. learns', 'B. learned', 'C. has learned', 'D. will learn']
            base['answer'] = 'C'
            base['explanation'] = 'since引导时间状语，主句用现在完成时'
            base['steps'] = ['since+过去时间→现在完成时', 'has/have+过去分词', 'has learned']
        elif '定语从句' in topic:
            base['question'] = 'The book ______ I bought yesterday is very interesting.'
            base['options'] = ['A. who', 'B. which', 'C. what', 'D. where']
            base['answer'] = 'B'
            base['explanation'] = '定语从句修饰物(the book)，用which/that'
            base['steps'] = ['先行词the book(物)', '关系词在从句中作宾语', 'which/that']
        else:
            base['question'] = f'（{topic}）Choose the correct answer: I enjoy ______ basketball.'
            base['options'] = ['A. play', 'B. playing', 'C. to play', 'D. played']
            base['answer'] = 'B'
            base['explanation'] = 'enjoy后接动名词(doing)'
            base['steps'] = ['enjoy+doing', 'playing']

    # 生物模板
    elif subject == 'bio':
        if '光合作用' in topic:
            base['question'] = '光合作用的原料是（  ）'
            base['options'] = ['A. 有机物和O₂', 'B. CO₂和H₂O', 'C. 有机物和CO₂', 'D. O₂和H₂O']
            base['answer'] = 'B'
            base['explanation'] = '6CO₂+6H₂O→C₆H₁₂O₆+6O₂'
            base['steps'] = ['光合作用公式', '原料：CO₂+H₂O', '产物：葡萄糖+O₂']
        elif '遗传' in topic:
            base['question'] = 'Aa×Aa后代中纯合子的比例为（  ）'
            base['options'] = ['A. 1/4', 'B. 1/2', 'C. 3/4', 'D. 1']
            base['answer'] = 'B'
            base['explanation'] = 'Aa×Aa→AA:Aa:aa=1:2:1，纯合子AA+aa=1/2'
            base['steps'] = ['Aa×Aa→1AA:2Aa:1aa', '纯合子=AA+aa=1/4+1/4', '=1/2']
        else:
            base['question'] = f'（{topic}）植物细胞不同于动物细胞的结构是（  ）'
            base['options'] = ['A. 细胞膜', 'B. 细胞质', 'C. 细胞核', 'D. 细胞壁']
            base['answer'] = 'D'
            base['explanation'] = '细胞壁是植物细胞特有的'
            base['steps'] = ['动植物细胞区别', '植物特有：细胞壁、液泡、叶绿体']

    # 语文模板
    elif subject == 'chin':
        if '成语' in topic:
            base['question'] = '下列成语使用正确的是（  ）'
            base['options'] = ['A. 他做事总是半途而废', 'B. 他成绩好真是差强人意', 'C. 这部剧首当其冲获奖', 'D. 他夸夸其谈获认可']
            base['answer'] = 'A'
            base['explanation'] = '半途而废：做事中途停止，使用正确。B差强人意=勉强满意；C首当其冲=最先受害；D夸夸其谈=贬义。'
            base['steps'] = ['A. 半途而废（中途放弃）✓', 'B. 差强人意（勉强满意）✗', 'C. 首当其冲（最先受害）✗', 'D. 夸夸其谈（浮夸）✗']
        else:
            base['question'] = f'（{topic}）"温故而知新"中"故"的意思是（  ）'
            base['options'] = ['A. 故事', 'B. 旧知识', 'C. 故意', 'D. 原因']
            base['answer'] = 'B'
            base['explanation'] = '出自《论语》，温习旧知识获得新体会'
            base['steps'] = ['论语·为政', '温故=温习旧知识', '知新=获得新体会']

    # 历史模板
    elif subject == 'hist':
        base['question'] = f'（{topic}）中国历史上第一个统一的封建王朝是（  ）'
        base['options'] = ['A. 夏朝', 'B. 商朝', 'C. 秦朝', 'D. 汉朝']
        base['answer'] = 'C'
        base['explanation'] = '公元前221年秦灭六国，建立第一个统一的中央集权封建王朝'
        base['steps'] = ['秦灭六国：前230-前221', '建立秦朝', '中央集权制度']

    # 地理模板
    elif subject == 'geo':
        base['question'] = f'（{topic}）我国面积最大的省级行政区是（  ）'
        base['options'] = ['A. 西藏', 'B. 内蒙古', 'C. 新疆', 'D. 青海']
        base['answer'] = 'C'
        base['explanation'] = '新疆面积约166万km²'
        base['steps'] = ['新疆166万km²', '西藏122万km²', '内蒙古118万km²']

    # 政治模板
    elif subject == 'poli':
        base['question'] = f'（{topic}）我国宪法规定一切权力属于（  ）'
        base['options'] = ['A. 公民', 'B. 人民', 'C. 政府', 'D. 政党']
        base['answer'] = 'B'
        base['explanation'] = '宪法第2条：一切权力属于人民'
        base['steps'] = ['宪法第2条', '一切权力属于人民']

    else:
        return None

    return base


# ═══════════════════════════════════════════
# DeepSeek API 生成（需API Key）
# ═══════════════════════════════════════════

def generate_with_deepseek(grade, subject, count=20, qtype='选择题'):
    """使用DeepSeek API批量生成题目"""
    api_key = os.environ.get('DEEPSEEK_API_KEY')
    if not api_key:
        print("❌ 请设置环境变量: export DEEPSEEK_API_KEY='sk-xxx'")
        print("   获取Key: https://platform.deepseek.com/api_keys")
        return []

    topics = CURRICULUM.get(grade, {}).get(subject, ['综合'])
    topics_str = '、'.join(topics[:10])

    prompt = f"""请生成{count}道{grade}{subject}学科的{qtype}。

知识点覆盖：{topics_str}

要求：
1. 题目符合{grade}真实教学大纲和考试要求
2. 每题包含：题目、4个选项(A/B/C/D)、正确答案、详细解析、解题步骤
3. 输出纯JSON数组格式

JSON格式示例：
[
  {{
    "topic": "知识点名称",
    "question": "题目内容",
    "options": ["A. 选项A", "B. 选项B", "C. 选项C", "D. 选项D"],
    "answer": "A",
    "explanation": "详细解析",
    "steps": ["步骤1", "步骤2", "步骤3"]
  }}
]

只输出JSON数组，不要其他内容。"""

    try:
        import requests
        resp = requests.post(
            'https://api.deepseek.com/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'model': 'deepseek-chat',
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.8,
                'max_tokens': 4096,
            },
            timeout=120
        )

        if resp.status_code == 200:
            content = resp.json()['choices'][0]['message']['content']
            # 提取JSON
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                questions = json.loads(json_match.group())
                # 添加元数据
                for i, q in enumerate(questions):
                    q['id'] = f'ds{grade[0]}{subject[0]}{i}'
                    q['year'] = 2024
                    q['grade'] = grade
                    q['subject'] = subject
                    q['type'] = qtype
                    q['difficulty'] = 3
                    q['source'] = 'DeepSeek生成'
                return questions
        else:
            print(f"  ❌ DeepSeek API错误: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        print(f"  ❌ 请求失败: {e}")

    return []


# ═══════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description='题目生成器')
    parser.add_argument('--grade', '-g', help='年级')
    parser.add_argument('--subject', '-s', help='科目')
    parser.add_argument('--count', '-n', type=int, default=15, help='每科生成数量')
    parser.add_argument('--type', '-t', default='选择题', help='题型')
    parser.add_argument('--all', action='store_true', help='生成全部年级全部科目')
    parser.add_argument('--replace', action='store_true', help='替换网站data.js中的demo数据')
    parser.add_argument('--deepseek', action='store_true', help='使用DeepSeek API生成（需API Key）')
    parser.add_argument('--output', '-o', default=None, help='输出文件')

    args = parser.parse_args()

    if args.all:
        all_questions = {}
        grades = ['初中', '高一', '高二']
        for grade in grades:
            all_questions[grade] = {}
            for subject in CURRICULUM[grade].keys():
                if args.deepseek:
                    qs = generate_with_deepseek(grade, subject, args.count, args.type)
                else:
                    qs = generate_builtin(grade, subject, args.count)
                all_questions[grade][subject] = qs
                print(f"  {grade}·{subject}: {len(qs)}题")

        if args.replace:
            replace_demo_data(all_questions)
        else:
            output = args.output or '/tmp/generated_questions.json'
            with open(output, 'w', encoding='utf-8') as f:
                json.dump(all_questions, f, ensure_ascii=False, indent=2)
            print(f"\n✅ 已导出到 {output}")
            print(f"💡 运行以下命令替换网站数据:")
            print(f"   python3 generate_questions.py --all --replace")

    elif args.grade and args.subject:
        if args.deepseek:
            qs = generate_with_deepseek(args.grade, args.subject, args.count, args.type)
        else:
            qs = generate_builtin(args.grade, args.subject, args.count)
        print(f"✅ {args.grade}·{args.subject}: {len(qs)}题")

        if args.replace:
            all_qs = {args.grade: {args.subject: qs}}
            replace_demo_data(all_qs)
        elif args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(qs, f, ensure_ascii=False, indent=2)

    else:
        parser.print_help()
        print("\n💡 快速开始:")
        print("   python3 generate_questions.py --all           # 生成全部（内置题库）")
        print("   python3 generate_questions.py --all --replace # 生成并替换网站demo")
        print("   python3 generate_questions.py --all --deepseek # 用DeepSeek API生成")


def replace_demo_data(all_questions):
    """替换data.js中的demo数据"""
    data_path = '/Users/luan/Desktop/ai教学/教育网站/js/data.js'
    with open(data_path, 'r') as f:
        content = f.read()

    grade_var_map = {'初中': 'DEMO_CHUZHONG', '高一': 'DEMO_GAOYI', '高二': 'DEMO_GAOER'}

    for grade, subjects in all_questions.items():
        var_name = grade_var_map[grade]
        # 构建JS代码
        js_parts = [f'{var_name} = {{']
        for subject, questions in subjects.items():
            if not questions:
                continue
            js_parts.append(f'  {subject}: [')
            for q in questions:
                esc = lambda s: str(s).replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')
                opts_js = '[' + ', '.join(f'`{esc(opt)}`' for opt in q.get('options', [])) + ']'
                steps_js = '[' + ', '.join(f'`{esc(s)}`' for s in q.get('steps', [])) + ']'
                js_parts.append(f"    {{ id:'{q['id']}',year:{q.get('year',2024)},grade:'{grade}',subject:'{subject}',type:'{q.get('type','选择题')}',difficulty:{q.get('difficulty',2)},topic:`{esc(q.get('topic',''))}`,question:`{esc(q['question'])}`,options:{opts_js},answer:`{esc(str(q.get('answer','')))}`,explanation:`{esc(q.get('explanation',''))}`,steps:{steps_js} }},")
            js_parts.append('  ],')
        js_parts.append('};')
        new_block = '\n'.join(js_parts)

        # 在data.js中替换对应变量
        import re
        pattern = rf'const {var_name} = {{.*?}};'
        content = re.sub(pattern, new_block, content, flags=re.DOTALL)

    with open(data_path, 'w') as f:
        f.write(content)

    print(f"✅ data.js 已更新")


if __name__ == '__main__':
    main()
