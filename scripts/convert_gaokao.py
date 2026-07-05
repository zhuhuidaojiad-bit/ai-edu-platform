#!/usr/bin/env python3
"""
Convert GAOKAO-Bench dataset to website-compatible JS format.
Parses LaTeX-formatted questions, extracts options, and generates structured data.
"""

import json
import re
import os
import sys

# ── Text Cleaning ──────────────────────────────────────────
def clean_text(text):
    """Clean Chinese text: normalize spaces, remove artifacts."""
    # Replace full-width space (U+3000) with normal space
    text = text.replace('\u3000', ' ')
    # Collapse multiple spaces/newlines into single space
    import re
    text = re.sub(r'[ \t\n\r]+', ' ', text)
    # Remove leading question numbers like "7．（ 3分）" or "1．（ 9分）"
    text = re.sub(r'^[\d一二三四五六七八九十]+[．\.、]\s*(?:[（(]\s*\d+\s*分[）)])?\s*', '', text)
    # Clean up excessive punctuation spacing
    text = re.sub(r'\s*[，。；：、！？]\s*', lambda m: m.group().strip()+' ', text)
    # Final trim
    text = text.strip()
    return text

# ── Subject Mapping ──────────────────────────────────────────
# Map source filenames / categories to website subject codes
SUBJECT_MAP = {
    'Math_I_MCQ': 'math',
    'Math_II_MCQ': 'math',
    'Math_I_Fill': 'math',
    'Math_II_Fill': 'math',
    'Physics_MCQ': 'phys',
    'Chemistry_MCQ': 'chem',
    'Biology_MCQ': 'bio',
    'English_MCQ': 'engl',
    'English_Fill': 'engl',
    'English_Cloze': 'engl',
    'Chinese_Lang': 'chin',
    'Chinese_Lit': 'chin',
    'Geography_MCQ': 'geo',
    'History_MCQ': 'hist',
    'Politics_MCQ': 'poli',
    'Math_I_Open': 'math',
    'Math_II_Open': 'math',
    'Physics_Open': 'phys',
    'Chemistry_Open': 'chem',
    'Biology_Open': 'bio',
    'English_Error': 'engl',
    'English_Cloze2': 'engl',
}

# ── Topic Extraction ─────────────────────────────────────────
# Simple keyword-based topic detection from question text
TOPIC_KEYWORDS = {
    'math': [
        ('集合', '集合与逻辑'),
        ('复数', '复数'),
        ('向量', '平面向量'),
        ('数列', '数列'),
        ('三角函数', '三角函数'),
        ('三角', '三角函数'),
        ('函数', '函数与导数'),
        ('导数', '函数与导数'),
        ('积分', '函数与导数'),
        ('概率', '概率统计'),
        ('统计', '概率统计'),
        ('排列', '排列组合'),
        ('组合', '排列组合'),
        ('椭圆', '解析几何'),
        ('双曲线', '解析几何'),
        ('抛物线', '解析几何'),
        ('圆', '解析几何'),
        ('直线', '解析几何'),
        ('立体几何', '立体几何'),
        ('空间', '立体几何'),
        ('不等式', '不等式'),
        ('极限', '函数与导数'),
        ('曲线', '解析几何'),
        ('几何', '解析几何'),
        ('方程', '方程与函数'),
        ('框图', '算法与框图'),
        ('程序', '算法与框图'),
        ('二项式', '排列组合'),
        ('向量', '平面向量'),
    ],
    'phys': [
        ('力学', '力学'),
        ('运动', '运动学'),
        ('力', '力学'),
        ('牛顿', '力学'),
        ('能量', '力学'),
        ('动量', '力学'),
        ('电磁', '电磁学'),
        ('电场', '电磁学'),
        ('磁场', '电磁学'),
        ('电流', '电磁学'),
        ('感应', '电磁感应'),
        ('热', '热学'),
        ('光学', '光学'),
        ('光', '光学'),
        ('原子', '原子物理'),
        ('核', '原子物理'),
        ('波', '振动与波'),
        ('振动', '振动与波'),
        ('万有引力', '万有引力'),
        ('卫星', '万有引力'),
        ('天体', '万有引力'),
    ],
    'chem': [
        ('反应', '化学反应原理'),
        ('平衡', '化学平衡'),
        ('电解', '电化学'),
        ('原电池', '电化学'),
        ('电池', '电化学'),
        ('氧化还原', '氧化还原反应'),
        ('离子', '离子反应'),
        ('方程式', '化学方程式'),
        ('有机物', '有机化学'),
        ('有机', '有机化学'),
        ('元素', '元素化学'),
        ('周期', '元素周期律'),
        ('物质结构', '物质结构'),
        ('化学键', '物质结构'),
        ('溶液', '溶液与电解质'),
        ('酸', '酸碱反应'),
        ('碱', '酸碱反应'),
        ('实验', '化学实验'),
    ],
    'bio': [
        ('细胞', '细胞生物学'),
        ('光合', '光合作用'),
        ('呼吸', '细胞呼吸'),
        ('遗传', '遗传学'),
        ('基因', '遗传学'),
        ('DNA', '遗传学'),
        ('蛋白质', '分子生物学'),
        ('酶', '分子生物学'),
        ('免疫', '免疫学'),
        ('神经', '神经生物学'),
        ('激素', '内分泌'),
        ('生态', '生态学'),
        ('进化', '进化论'),
        ('种群', '生态学'),
        ('群落', '生态学'),
    ],
    'engl': [
        ('语法', '语法选择'),
        ('填空', '语法填空'),
        ('完形', '完形填空'),
        ('阅读', '阅读理解'),
        ('词汇', '词汇辨析'),
        ('时态', '时态语态'),
        ('从句', '从句'),
        ('对话', '情景对话'),
        ('写作', '书面表达'),
        ('改错', '短文改错'),
        ('七选五', '七选五阅读'),
    ],
    'hist': [
        ('分封', '中国古代政治'),
        ('专制', '中国古代政治'),
        ('革命', '中国近代史'),
        ('战争', '世界史'),
        ('改革', '制度变革'),
        ('工业', '经济史'),
        ('思想', '思想文化史'),
        ('制度', '政治制度'),
        ('经济', '经济史'),
        ('文化', '文化史'),
    ],
    'geo': [
        ('气候', '气候与天气'),
        ('地形', '地形地貌'),
        ('人口', '人口地理'),
        ('城市', '城市地理'),
        ('农业', '农业地理'),
        ('工业', '工业地理'),
        ('交通', '交通地理'),
        ('环境', '环境问题'),
        ('区域', '区域地理'),
        ('自然', '自然地理'),
    ],
    'poli': [
        ('经济', '经济常识'),
        ('政治', '政治制度'),
        ('哲学', '哲学常识'),
        ('文化', '文化生活'),
        ('法律', '法律常识'),
        ('国际', '国际政治'),
        ('市场', '市场经济'),
        ('政府', '政治制度'),
        ('民主', '政治制度'),
    ],
    'chin': [
        ('成语', '成语运用'),
        ('病句', '病句辨析'),
        ('文言', '文言文阅读'),
        ('诗歌', '诗歌鉴赏'),
        ('现代文', '现代文阅读'),
        ('语言', '语言运用'),
        ('字音', '字音字形'),
        ('词语', '词语运用'),
        ('衔接', '语句衔接'),
        ('得体', '语言得体'),
        ('图文', '图文转换'),
        ('写作', '作文'),
        ('名句', '名句默写'),
    ],
}


def extract_topic(subject, question_text):
    """Detect topic from question text using keywords."""
    keywords = TOPIC_KEYWORDS.get(subject, [])
    for keyword, topic in keywords:
        if keyword in question_text:
            return topic
    return {
        'math': '综合',
        'phys': '综合',
        'chem': '综合',
        'bio': '综合',
        'hist': '综合',
        'geo': '综合',
        'poli': '综合',
    }.get(subject, '综合')


def estimate_difficulty(index, total_in_paper):
    """Estimate difficulty from question position in the paper."""
    ratio = index / max(total_in_paper, 1)
    if ratio < 0.25:
        return 2
    elif ratio < 0.5:
        return 3
    elif ratio < 0.75:
        return 4
    else:
        return 5


def parse_options(question_text):
    """
    Extract options from question text.
    Returns (question_stem, options_list) where options_list is like ['A. xxx', 'B. xxx', ...]
    """
    # Pattern for A. B. C. D. options (Chinese-style separator)
    # Match common patterns: A. ... B. ... C. ... D. ...
    # Also handles: A． B． C． D． (fullwidth dots)

    text = question_text.strip()

    # Try various patterns to split options
    # Pattern 1: Standard "A.xxx B.xxx C.xxx D.xxx"
    option_patterns = [
        r'(?<=[）\)\s])A[\.．]\s*',  # A. or A．
        r'(?<=[）\)\s])A\s+',         # A followed by spaces
    ]

    # Find where options start
    opt_start = -1
    for pat in option_patterns:
        m = re.search(pat, text)
        if m:
            opt_start = m.start()
            break

    if opt_start == -1:
        return text, []

    stem = text[:opt_start].strip().rstrip('(').rstrip('（').strip()
    options_text = text[opt_start:]

    # Now split options
    # Match option markers: A. B. C. D. (or with LaTeX)
    option_splits = re.split(r'(?=[A-D][\.．]\s*)', options_text)

    options = []
    for opt in option_splits:
        opt = opt.strip()
        if opt and re.match(r'[A-D][\.．]', opt):
            options.append(opt)

    return stem, options


def split_chinese_lit(q, subject, base_id):
    """Split a Chinese Modern Lit passage into 3 individual sub-questions."""
    raw = q.get('question', '')
    analysis = q.get('analysis', '')
    answers = q.get('answer', [])
    year = q.get('year', 2010)
    category = q.get('category', '')

    # Find where sub-question 1 starts
    sq1_match = re.search(r'[（(]?1[）)．（(]', raw)
    if not sq1_match:
        return None

    passage = clean_text(raw[:sq1_match.start()])
    passage = re.sub(r'^[一二三]、[^\n]*\n?', '', passage).strip()

    sub_questions = []
    for sq_num in [1, 2, 3]:
        # Find this sub-question
        start_pat = r'[（(]?' + str(sq_num) + r'[）)．（(]'
        start_match = re.search(start_pat, raw)
        if not start_match:
            continue
        start = start_match.start()

        # Find end (next sub-question or end of text)
        if sq_num < 3:
            next_pat = r'[（(]?' + str(sq_num + 1) + r'[）)．（(]'
            end_match = re.search(next_pat, raw[start+3:])
            end = start + 3 + end_match.start() if end_match else len(raw)
        else:
            end = len(raw)

        sq_text = clean_text(raw[start:end])
        # Remove sub-question number prefix
        sq_text = re.sub(r'^[（(]?' + str(sq_num) + r'[）)．（(]\s*(?:\d+\s*分[）)])?\s*', '', sq_text).strip()

        # Parse options
        stem, opts = parse_options(sq_text)

        # Answer
        ans_idx = sq_num - 1
        ans_letter = answers[ans_idx] if ans_idx < len(answers) else '?'

        # Question text
        full_q = f"【阅读下文，完成问题】\n{passage[:400]}...\n\n{sq_num}. {stem}"

        # Extract sub-analysis
        sub_analysis = ''
        anal_pat = r'[（(]\s*' + str(sq_num) + r'\s*[）)]\s*(.+?)(?=[（(]\s*[' + str(sq_num+1) + r'4]\s*[）)]|$)'
        anal_match = re.search(anal_pat, analysis, re.DOTALL)
        if anal_match:
            sub_analysis = clean_text(anal_match.group(1))

        sub_questions.append({
            'id': base_id + sq_num - 1,
            'year': year,
            'subject': subject,
            'type': '阅读理解',
            'difficulty': 4,
            'topic': '现代文阅读',
            'question': full_q,
            'options': opts,
            'answer': ans_letter,
            'explanation': sub_analysis or clean_text(analysis),
            'source': category.strip(),
        })

    return sub_questions if len(sub_questions) == 3 else None


def convert_questions(source_files, source_dir):
    """Convert all source files to website format."""
    all_questions = []
    question_id = 1

    for source_name, filepath in source_files.items():
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        examples = data.get('example', [])
        subject = SUBJECT_MAP.get(source_name, 'math')

        # Determine question type
        if 'Open' in source_name:
            qtype = '解答题'
        elif 'Error' in source_name:
            qtype = '短文改错'
        elif 'Cloze2' in source_name or 'Cloze_Passage' in source_name:
            qtype = '语法填空'
        elif 'Fill' in source_name:
            qtype = '完形填空' if 'English' in source_name else '填空题'
        elif 'Cloze' in source_name:
            qtype = '七选五阅读'
        elif 'Lit' in source_name:
            qtype = '阅读理解'
        elif 'Geography' in source_name or 'History' in source_name or 'Politics' in source_name:
            qtype = '选择题'
        else:
            qtype = '选择题'

        total_q = len(examples)
        print(f"  Converting {source_name}: {total_q} questions → subject={subject}, type={qtype}")

        for i, q in enumerate(examples):
            # For Chinese Lit: split passage into individual sub-questions
            if 'Lit' in source_name:
                lit_qs = split_chinese_lit(q, subject, question_id)
                if lit_qs:
                    all_questions.extend(lit_qs)
                    question_id += len(lit_qs)
                    continue

            raw_question = q.get('question', '')
            answer_list = q.get('answer', [])
            analysis = q.get('analysis', '')
            year = q.get('year', 2010)
            category = q.get('category', '')

            # Parse question stem and options
            stem, options = parse_options(raw_question)

            # Format answer
            if qtype == '选择题':
                answer_str = '、'.join(answer_list) if answer_list else '?'
            else:
                # Fill-in-the-blank: answer might be LaTeX
                answer_str = answer_list[0] if answer_list else '?'

            # Extract topic
            topic = extract_topic(subject, raw_question)

            # Estimate difficulty
            difficulty = estimate_difficulty(i, total_q)

            # Clean up question stem with clean_text
            stem = clean_text(stem)

            # Build website-format question
                        # Clean analysis text
            analysis = clean_text(analysis)

            website_q = {
                'id': question_id,
                'year': year,
                'subject': subject,
                'type': qtype,
                'difficulty': difficulty,
                'topic': topic,
                'question': stem,
                'options': options,
                'answer': answer_str,
                'explanation': analysis.strip(),
                'source': category.strip(),
            }

            all_questions.append(website_q)
            question_id += 1

    return all_questions


def js_string_literal(text):
    """Escape text for use inside a JS backtick template literal.
    Returns text safe for embedding in `...`."""
    # Escape backticks and dollar-brace (template interpolation)
    text = text.replace('\\', '\\\\')
    text = text.replace('`', '\\`')
    text = text.replace('${', '\\${')
    return text


def format_option_display(opt):
    """Format an option for JS display, preserving LaTeX."""
    return js_string_literal(opt)


def generate_js_file(questions, output_path):
    """Generate a JS data file with converted questions.
    Uses backtick template literals for multiline text fields."""
    lines = ['/* ========================================',]
    lines.append('   安徽高考真题库 — 来自 GAOKAO-Bench 开源数据集')
    lines.append('   总计 ' + str(len(questions)) + ' 道题 | 自动生成')
    lines.append('   ======================================== */')
    lines.append('')
    lines.append('var gaokaoQuestions = [')

    for q in questions:
        # Format options array - each option uses backtick for safety
        opts_parts = []
        for o in q['options']:
            opts_parts.append('`' + format_option_display(o) + '`')
        opts_js = '[' + ', '.join(opts_parts) + ']'

        # Use backtick template literals for multiline-safe fields
        q_text = js_string_literal(q['question'])
        q_expl = js_string_literal(q['explanation'])
        q_answer = js_string_literal(q['answer'])
        q_topic = js_string_literal(q['topic'])
        q_source = js_string_literal(q.get('source', ''))

        lines.append('  {')
        lines.append(f"    id: {q['id']}, year: {q['year']}, subject: '{q['subject']}', "
                     f"type: '{q['type']}', difficulty: {q['difficulty']},")
        lines.append(f"    topic: `{q_topic}`,")
        lines.append(f"    question: `{q_text}`,")
        lines.append(f"    options: {opts_js},")
        lines.append(f"    answer: `{q_answer}`,")
        lines.append(f"    explanation: `{q_expl}`,")
        lines.append(f"    source: `{q_source}`")
        lines.append('  },')

    lines.append('];')

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"\n✅ Generated: {output_path}")
    print(f"   Total questions: {len(questions)}")

    # Stats
    subjects = {}
    for q in questions:
        s = q['subject']
        subjects[s] = subjects.get(s, 0) + 1
    print("   By subject:")
    for s, c in sorted(subjects.items()):
        print(f"     {s}: {c}")


def main():
    source_dir = '/tmp'
    source_files = {
        'Math_I_MCQ':     os.path.join(source_dir, '2010-2022_Math_I_MCQs.json'),
        'Math_II_MCQ':    os.path.join(source_dir, '2010-2022_Math_II_MCQs.json'),
        'Physics_MCQ':    os.path.join(source_dir, 'physics_mcq.json'),
        'Chemistry_MCQ':  os.path.join(source_dir, '2010-2022_Chemistry_MCQs.json'),
        'Biology_MCQ':    os.path.join(source_dir, '2010-2022_Biology_MCQs.json'),
        'Math_I_Fill':    os.path.join(source_dir, '2010-2022_Math_I_Fill-in-the-Blank.json'),
        'Math_II_Fill':   os.path.join(source_dir, '2010-2022_Math_II_Fill-in-the-Blank.json'),
        'English_MCQ':    os.path.join(source_dir, '2010-2013_English_MCQs.json'),
        'English_Fill':   os.path.join(source_dir, '2010-2022_English_Fill_in_Blanks.json'),
        'English_Cloze':  os.path.join(source_dir, '2012-2022_English_Cloze_Test.json'),
        'Chinese_Lang':   os.path.join(source_dir, '2010-2022_Chinese_Lang_and_Usage_MCQs.json'),
        'Chinese_Lit':    os.path.join(source_dir, '2010-2022_Chinese_Modern_Lit.json'),
        'Geography_MCQ':  os.path.join(source_dir, '2010-2022_Geography_MCQs.json'),
        'History_MCQ':    os.path.join(source_dir, '2010-2022_History_MCQs.json'),
        'Politics_MCQ':   os.path.join(source_dir, '2010-2022_Political_Science_MCQs.json'),
        'Math_I_Open':    os.path.join(source_dir, '2010-2022_Math_I_Open-ended_Questions.json'),
        'Math_II_Open':   os.path.join(source_dir, '2010-2022_Math_II_Open-ended_Questions.json'),
        'Physics_Open':   os.path.join(source_dir, '2010-2022_Physics_Open-ended_Questions.json'),
        'Chemistry_Open': os.path.join(source_dir, '2010-2022_Chemistry_Open-ended_Questions.json'),
        'Biology_Open':   os.path.join(source_dir, '2010-2022_Biology_Open-ended_Questions.json'),
        'English_Error':  os.path.join(source_dir, '2012-2022_English_Language_Error_Correction.json'),
        'English_Cloze2': os.path.join(source_dir, '2014-2022_English_Language_Cloze_Passage.json'),
    }

    print("🔍 Converting GAOKAO-Bench dataset...")
    questions = convert_questions(source_files, source_dir)

    output = '/Users/luan/Desktop/ai教学/教育网站/js/gaokao_questions.js'
    generate_js_file(questions, output)

    # Also generate a summary
    print(f"\n📊 Dataset Summary:")
    print(f"   Total: {len(questions)} questions")
    years = sorted(set(q['year'] for q in questions))
    print(f"   Years: {years[0]}-{years[-1]}")


if __name__ == '__main__':
    main()
