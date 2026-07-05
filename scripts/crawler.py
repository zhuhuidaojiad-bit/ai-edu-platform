#!/usr/bin/env python3
"""
题库数据管理工具 — 拉取开源题库、处理本地文件、更新网站数据

使用方法：
  # 1. 列出所有已知开源题库
  python3 crawler.py --list

  # 2. 拉取指定开源数据集并转换
  python3 crawler.py --fetch qzdh        # QZDH 数学物理 675题
  python3 crawler.py --fetch gaokao-mm   # GAOKAO-MM 多模态 646题

  # 3. 从本地PDF/Word提取题目（需安装pymupdf/python-docx）
  python3 crawler.py --local ./my_exams/ --grade 高一 --subject math

  # 4. 更新网站数据文件（整合所有数据源）
  python3 crawler.py --build

  # 5. 添加自定义题目（JSON格式）
  python3 crawler.py --import questions.json --grade 初中
"""

import requests
import json
import re
import time
import os
import sys
import argparse
import subprocess
from collections import defaultdict
from urllib.parse import urljoin

# ═══════════════════════════════════════════
# 已知开源题库资源
# ═══════════════════════════════════════════

KNOWN_SOURCES = {
    'gaokao-bench': {
        'name': 'GAOKAO-Bench (OpenLMLab)',
        'url': 'https://github.com/OpenLMLab/GAOKAO-Bench',
        'type': 'github-json',
        'size': '2,811题',
        'grades': ['高三'],
        'subjects': '全科',
        'status': '✅ 已集成 (2,290题)',
        'notes': '2010-2022年高考真题，学术基准数据集'
    },
    'qzdh': {
        'name': '求知导航高考数据',
        'url': 'https://github.com/gdshjzm/QZDH_Gaokao-data',
        'type': 'github-json',
        'size': '675题',
        'grades': ['高三'],
        'subjects': '数学、物理',
        'status': '⬇️ 待拉取',
        'notes': '含DeepSeek-R1生成的详细解析，JSON格式'
    },
    'gaokao-mm': {
        'name': 'GAOKAO-MM (OpenMOSS)',
        'url': 'https://github.com/OpenMOSS/GAOKAO-MM',
        'type': 'github-json',
        'size': '646题',
        'grades': ['高三'],
        'subjects': '8学科（含图片题）',
        'status': '⬇️ 待拉取',
        'notes': '多模态高考题，含数学几何图、物理实验图等'
    },
    'agieval': {
        'name': 'AGIEval Benchmark',
        'url': 'https://github.com/ruixiangcui/AGIEval',
        'type': 'github-json',
        'size': '含高考/中考题',
        'grades': ['初中', '高三'],
        'subjects': '多科',
        'status': '⬇️ 待拉取',
        'notes': '包含中考和高考题，需筛选'
    },
    'xkw-api': {
        'name': '学科网开放平台',
        'url': 'https://open.xkw.com',
        'type': 'api',
        'size': '千万级',
        'grades': ['初中','高一','高二','高三'],
        'subjects': '全科',
        'status': '🔑 需注册API Key',
        'notes': '最全的K12题库API，支持按年级/科目/题型筛选'
    },
    'jyeoo-api': {
        'name': '菁优网开放平台',
        'url': 'https://www.jyeoo.com/open',
        'type': 'api',
        'size': '千万级',
        'grades': ['初中','高一','高二','高三'],
        'subjects': '全科',
        'status': '🔑 需注册API Key',
        'notes': '老牌题库API，支持按省份/年份筛选'
    },
}

# ═══════════════════════════════════════════
# GitHub数据拉取
# ═══════════════════════════════════════════

GITHUB_HEADERS = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/vnd.github.v3+json',
}

def fetch_github_json(repo, data_dir='/tmp/exam_data'):
    """从GitHub仓库拉取JSON数据文件"""
    repo_name = repo.split('/')[-1]
    target = os.path.join(data_dir, repo_name)

    if os.path.exists(target):
        print(f"  📁 已存在: {target}")
    else:
        print(f"  📥 克隆 {repo} ...")
        result = subprocess.run(
            ['git', 'clone', '--depth', '1', repo, target],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            print(f"  ❌ 克隆失败: {result.stderr[:200]}")
            return None
        print(f"  ✅ 克隆成功")

    # 查找所有JSON文件
    json_files = []
    for root, dirs, files in os.walk(target):
        for f in files:
            if f.endswith('.json') and f != '.DS_Store':
                json_files.append(os.path.join(root, f))

    print(f"  📄 找到 {len(json_files)} 个JSON文件")
    return json_files


def convert_qzdh_data(json_files, output_dir):
    """转换QZDH Gaokao数据为网站格式"""
    all_questions = []
    qid = 10000  # Start from high ID to avoid conflicts

    for fpath in json_files:
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            continue

        if not isinstance(data, list):
            continue

        for item in data:
            if not isinstance(item, dict):
                continue

            # Map subject
            subject = 'math'
            q_text = item.get('question', '')
            if '物理' in q_text or '力' in q_text or '电' in q_text:
                subject = 'phys'

            # Map grade (QZDH is all Gaokao = 高三)
            grade = '高三'

            # Extract answer
            answer = item.get('corr-ans', item.get('answer', '?'))

            # Extract explanation (DeepSeek generated)
            explanation = item.get('answer', '')  # DeepSeek's full answer

            qid += 1
            all_questions.append({
                'id': qid,
                'year': 2023,
                'grade': grade,
                'subject': subject,
                'type': '解答题',
                'difficulty': 4,
                'topic': '综合',
                'question': q_text[:500],
                'options': [],
                'answer': str(answer),
                'explanation': str(explanation)[:800],
                'source': 'QZDH开源数据集',
            })

    print(f"  ✅ 转换 {len(all_questions)} 道题")
    return all_questions


# ═══════════════════════════════════════════
# 本地文件处理
# ═══════════════════════════════════════════

def process_local_files(directory, grade, subject):
    """处理本地题库文件（JSON/CSV/PDF）"""
    questions = []
    qid = 50000

    for fname in os.listdir(directory):
        fpath = os.path.join(directory, fname)

        if fname.endswith('.json'):
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if isinstance(data, list):
                for item in data:
                    qid += 1
                    questions.append({
                        'id': qid,
                        'year': item.get('year', 2024),
                        'grade': grade,
                        'subject': subject,
                        'type': item.get('type', '选择题'),
                        'difficulty': item.get('difficulty', 3),
                        'topic': item.get('topic', ''),
                        'question': item.get('question', ''),
                        'options': item.get('options', []),
                        'answer': str(item.get('answer', '')),
                        'explanation': item.get('explanation', ''),
                        'source': f'本地导入·{fname}',
                    })
        elif fname.endswith('.csv'):
            import csv
            with open(fpath, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    qid += 1
                    questions.append({
                        'id': qid,
                        'year': int(row.get('year', 2024)),
                        'grade': grade,
                        'subject': subject,
                        'type': row.get('type', '选择题'),
                        'difficulty': int(row.get('difficulty', 3)),
                        'topic': row.get('topic', ''),
                        'question': row.get('question', ''),
                        'options': json.loads(row.get('options', '[]')),
                        'answer': row.get('answer', ''),
                        'explanation': row.get('explanation', ''),
                        'source': f'本地导入·{fname}',
                    })

    print(f"  ✅ 从 {directory} 导入 {len(questions)} 道题")
    return questions


# ═══════════════════════════════════════════
# 网站数据构建
# ═══════════════════════════════════════════

def build_website_data(extra_sources=None):
    """构建完整的网站数据文件"""
    website_dir = '/Users/luan/Desktop/ai教学/教育网站'
    output_path = os.path.join(website_dir, 'js/gaokao_questions.js')

    print("🔨 构建网站数据...")

    # 1. GAOKAO-Bench is already built (run convert_gaokao.py)
    print("  1. 运行 GAOKAO-Bench 转换...")
    convert_script = os.path.join(website_dir, 'scripts/convert_gaokao.py')
    result = subprocess.run(['python3', convert_script], capture_output=True, text=True)
    if result.returncode == 0:
        for line in result.stdout.split('\n'):
            if 'Total questions' in line or 'By subject' in line or 'bio:' in line:
                print(f"     {line.strip()}")
    else:
        print(f"     ❌ 转换失败: {result.stderr[:200]}")

    # 2. Check for extra data sources
    if extra_sources:
        for source in extra_sources:
            print(f"  2. 合并额外数据源: {source}")
            with open(source, 'r') as f:
                extra = json.load(f)
            print(f"     +{len(extra)} 道题")

    # 3. Print summary
    with open(output_path, 'r') as f:
        content = f.read()
    total = len(re.findall(r"id: \d+", content))
    subjects = re.findall(r"subject: '(\w+)'", content)
    sc = defaultdict(int)
    for s in subjects:
        sc[s] += 1

    print(f"\n📊 网站题库摘要: {total} 题")
    for s, c in sorted(sc.items(), key=lambda x: -x[1]):
        print(f"   {s}: {c}")
    print(f"\n✅ 数据文件: {output_path}")


# ═══════════════════════════════════════════
# 题目模板生成器（比纯demo好）
# ═══════════════════════════════════════════

def generate_from_template(grade, subject, count=20):
    """基于知识图谱生成结构化题目模板"""
    templates = {
        ('初中', 'math'): [
            {'topic': '有理数运算', 'q': '计算：(-3)² + (-2)³ - |-5| = ?', 'a': '-4'},
            {'topic': '一元一次方程', 'q': '方程 3x - 7 = 2x + 5 的解是', 'a': '12'},
            {'topic': '二元一次方程组', 'q': '解方程组：x+y=5, 2x-y=1', 'a': 'x=2,y=3'},
            {'topic': '不等式', 'q': '不等式 2x - 3 > 5 的解集是', 'a': 'x>4'},
            {'topic': '平面直角坐标系', 'q': '点P(3,-4)到x轴的距离是', 'a': '4'},
            {'topic': '一次函数', 'q': '函数 y=2x+1 的图象经过第几象限', 'a': '一、二、三'},
            {'topic': '三角形', 'q': '等腰三角形顶角为80°，则底角为', 'a': '50°'},
            {'topic': '全等三角形', 'q': '判定三角形全等的方法不包括', 'a': 'SSA'},
            {'topic': '勾股定理', 'q': '直角边3和4的直角三角形斜边长为', 'a': '5'},
            {'topic': '平行四边形', 'q': '平行四边形的对角线', 'a': '互相平分'},
        ],
    }

    key = (grade, subject)
    if key not in templates:
        return []

    questions = []
    for i, t in enumerate(templates[key]):
        questions.append({
            'id': f't{grade[0]}{subject[0]}{i}',
            'year': 2024,
            'grade': grade,
            'subject': subject,
            'type': '填空题',
            'difficulty': 2,
            'topic': t['topic'],
            'question': t['q'],
            'options': [],
            'answer': t['a'],
            'explanation': f'本题考查{t["topic"]}的基础知识。',
            'steps': [f'识别考点：{t["topic"]}', '运用相关公式/定理计算', f'得出答案：{t["a"]}'],
            'source': '知识点模板',
        })
    return questions


# ═══════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='题库数据管理工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 crawler.py --list                # 列出所有数据源
  python3 crawler.py --fetch qzdh          # 拉取QZDH数据集
  python3 crawler.py --fetch gaokao-mm     # 拉取GAOKAO-MM
  python3 crawler.py --local ./exams/ -g 高一 -s math  # 导入本地文件
  python3 crawler.py --build               # 重新构建网站数据
  python3 crawler.py --template -g 初中 -s math -n 10  # 生成模板题目
  python3 crawler.py --import questions.json -g 初中   # 导入JSON题库
        """
    )

    parser.add_argument('--list', action='store_true', help='列出所有数据源')
    parser.add_argument('--fetch', help='拉取指定数据集 (qzdh/gaokao-mm/agieval)')
    parser.add_argument('--local', help='导入本地题目目录')
    parser.add_argument('-g', '--grade', help='年级 (初中/高一/高二/高三)')
    parser.add_argument('-s', '--subject', help='科目 (math/phys/chem/bio/engl/chin/hist/geo/poli)')
    parser.add_argument('--build', action='store_true', help='重新构建网站数据')
    parser.add_argument('--template', action='store_true', help='生成模板题目')
    parser.add_argument('-n', '--count', type=int, default=20, help='生成题目数量')
    parser.add_argument('--import', dest='import_file', help='导入JSON题库文件')
    parser.add_argument('--output', default=None, help='输出文件路径')

    args = parser.parse_args()

    # 列表模式
    if args.list:
        print("\n📚 已知题库资源:\n")
        for key, info in KNOWN_SOURCES.items():
            print(f"  [{key}] {info['name']}")
            print(f"    地址: {info['url']}")
            print(f"    规模: {info['size']} | 年级: {','.join(info['grades'])}")
            print(f"    状态: {info['status']}")
            print(f"    说明: {info['notes']}")
            print()
        print("💡 使用 --fetch <key> 拉取对应数据集")
        return

    # 拉取模式
    if args.fetch:
        key = args.fetch
        if key not in KNOWN_SOURCES:
            print(f"❌ 未知数据源: {key}")
            print(f"可用: {list(KNOWN_SOURCES.keys())}")
            return

        source = KNOWN_SOURCES[key]
        print(f"\n📥 拉取: {source['name']}")

        if key == 'qzdh':
            json_files = fetch_github_json('https://github.com/gdshjzm/QZDH_Gaokao-data')
            if json_files:
                questions = convert_qzdh_data(json_files, '/tmp')
                output = args.output or '/tmp/qzdh_converted.js'
                export_js(questions, output)
                print(f"\n💡 运行以下命令导入网站:")
                print(f"   python3 crawler.py --import {output} -g 高三")

        elif key == 'gaokao-mm':
            json_files = fetch_github_json('https://github.com/OpenMOSS/GAOKAO-MM')
            if json_files:
                print(f"   ⚠️ GAOKAO-MM 含图片题，需手动处理图片URL")

        elif key == 'agieval':
            json_files = fetch_github_json('https://github.com/ruixiangcui/AGIEval')
            if json_files:
                print(f"   📄 找到数据文件，需筛选中考/高考题")

        return

    # 本地导入
    if args.local:
        if not args.grade:
            print("❌ 需要指定 --grade")
            return
        questions = process_local_files(args.local, args.grade, args.subject or 'math')
        output = args.output or f'/tmp/imported_{args.grade}_{args.subject}.js'
        export_js(questions, output)
        return

    # 模板生成
    if args.template:
        if not args.grade or not args.subject:
            print("❌ 需要指定 --grade 和 --subject")
            return
        questions = generate_from_template(args.grade, args.subject, args.count)
        output = args.output or f'/tmp/template_{args.grade}_{args.subject}.js'
        export_js(questions, output)
        print(f"\n💡 运行以下命令导入网站:")
        print(f"   python3 crawler.py --import {output} -g {args.grade}")
        return

    # JSON导入
    if args.import_file:
        if not args.grade:
            print("❌ 需要指定 --grade")
            return
        with open(args.import_file, 'r') as f:
            questions = json.load(f)
        # Merge into data.js
        merge_into_data_js(questions, args.grade)
        return

    # 构建模式
    if args.build:
        build_website_data()
        return

    # 默认: 显示帮助
    parser.print_help()
    print("\n💡 提示: 使用 --list 查看所有可用数据源")


def export_js(questions, output_path):
    """导出为JS格式"""
    lines = ['var exportedQuestions = [']

    def esc(s):
        s = str(s)
        s = s.replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')
        return s

    for q in questions:
        opts = q.get('options', [])
        opts_js = '[' + ', '.join(f'`{esc(str(o))}`' for o in opts) + ']'
        lines.append('  {')
        lines.append(f"    id: '{q.get('id')}', year: {q.get('year', 2024)}, grade: '{q.get('grade')}', subject: '{q.get('subject')}',")
        lines.append(f"    type: '{q.get('type', '选择题')}', difficulty: {q.get('difficulty', 3)},")
        lines.append(f"    topic: `{esc(q.get('topic', ''))}`,")
        lines.append(f"    question: `{esc(q.get('question', ''))}`,")
        lines.append(f"    options: {opts_js},")
        lines.append(f"    answer: `{esc(str(q.get('answer', '')))}`,")
        lines.append(f"    explanation: `{esc(q.get('explanation', ''))}`,")
        lines.append(f"    source: `{esc(q.get('source', ''))}`")
        lines.append('  },')

    lines.append('];')

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"✅ 导出 {len(questions)} 题 → {output_path}")


def merge_into_data_js(questions, grade):
    """合并题目到data.js"""
    data_path = '/Users/luan/Desktop/ai教学/教育网站/js/data.js'
    with open(data_path, 'r') as f:
        content = f.read()

    # Find the DEMO section for this grade and add questions
    grade_map = {'初中': 'DEMO_CHUZHONG', '高一': 'DEMO_GAOYI', '高二': 'DEMO_GAOER', '高三': 'DEMO_2025'}
    var_name = grade_map.get(grade)

    # For now, create a separate file
    output = f'/tmp/merge_{grade}.js'
    export_js(questions, output)
    print(f"\n📋 题目已导出到 {output}")
    print(f"   请手动添加到 data.js 的 {var_name} 中")


if __name__ == '__main__':
    main()
