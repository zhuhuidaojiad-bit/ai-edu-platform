"""Fix Chinese Lit parsing - split multi-question passages."""
import re

path = '/Users/luan/Desktop/ai教学/教育网站/scripts/convert_gaokao.py'
with open(path) as f:
    content = f.read()

# 1. Add split_chinese_lit function before convert_questions
old = "def convert_questions(source_files, source_dir):"

new_func = '''def split_chinese_lit(q, subject, base_id):
    """Split a Chinese Modern Lit passage into 3 individual sub-questions."""
    raw = q.get('question', '')
    analysis = q.get('analysis', '')
    answers = q.get('answer', [])
    year = q.get('year', 2010)
    category = q.get('category', '')

    # Find where sub-question 1 starts
    sq1_match = re.search(r'1[．（(]', raw)
    if not sq1_match:
        return None

    passage = clean_text(raw[:sq1_match.start()])
    passage = re.sub(r'^[一二三]、[^\n]+\n', '', passage).strip()

    sub_questions = []
    for sq_num in [1, 2, 3]:
        # Find this sub-question
        start_pat = str(sq_num) + r'[．（(]'
        start_match = re.search(start_pat, raw)
        if not start_match:
            continue
        start = start_match.start()

        # Find end (next sub-question or end of text)
        if sq_num < 3:
            next_pat = str(sq_num + 1) + r'[．（(]'
            end_match = re.search(next_pat, raw[start+3:])
            end = start + 3 + end_match.start() if end_match else len(raw)
        else:
            end = len(raw)

        sq_text = clean_text(raw[start:end])
        # Remove sub-question number prefix
        sq_text = re.sub(r'^' + str(sq_num) + r'[．（(]\s*(?:\d+\s*分[）)])?\s*', '', sq_text).strip()

        # Parse options
        stem, opts = parse_options(sq_text)

        # Answer
        ans_idx = sq_num - 1
        ans_letter = answers[ans_idx] if ans_idx < len(answers) else '?'

        # Question text
        full_q = f"【阅读下文，完成问题】\\n{passage[:400]}...\\n\\n{sq_num}. {stem}"

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


def convert_questions(source_files, source_dir):'''

content = content.replace(old, new_func)

# 2. Fix the Lit processing to split into sub-questions
old_lit = """        elif 'Lit' in source_name:
            qtype = '阅读理解'
        elif 'Geography' in source_name or 'History' in source_name or 'Politics' in source_name:
            qtype = '选择题'"""

new_lit = """        elif 'Lit' in source_name:
            qtype = '阅读理解'
            # Split Chinese Modern Lit into 3 individual sub-questions
            lit_qs = split_chinese_lit(q, subject, question_id)
            if lit_qs:
                all_questions.extend(lit_qs)
                question_id += len(lit_qs)
                continue
        elif 'Geography' in source_name or 'History' in source_name or 'Politics' in source_name:
            qtype = '选择题'"""

content = content.replace(old_lit, new_lit)

with open(path, 'w') as f:
    f.write(content)

print("✅ Chinese Lit splitting logic added to convert script")
