import streamlit as st
import pandas as pd
import os
import json
import shutil
import re

# ================= 配置与初始化 =================
st.set_page_config(page_title="刷题神器(MD修复版)", page_icon="♾️", layout="wide")

# 文件路径
HISTORY_FILE = "study_progress.json"
STATS_FILE = "study_stats.json"
COMBINED_BANK_FILE = "combined_bank.json"

# 初始化Session
if 'all_questions' not in st.session_state: st.session_state.all_questions = []
if 'wrong_questions' not in st.session_state: st.session_state.wrong_questions = set()

# 保留双进度逻辑 (不动)
if 'practice_index' not in st.session_state: st.session_state.practice_index = 0
if 'wrong_index' not in st.session_state: st.session_state.wrong_index = 0
if 'mode' not in st.session_state: st.session_state.mode = 'practice'
if 'stats' not in st.session_state: st.session_state.stats = {}


# ================= 文件存取 (不动) =================

def save_all_data():
    try:
        progress_data = {
            "wrong_questions": list(st.session_state.wrong_questions),
            "practice_index": st.session_state.practice_index,
            "wrong_index": st.session_state.wrong_index,
            "mode": st.session_state.mode
        }
        with open(HISTORY_FILE, "w", encoding='utf-8') as f:
            json.dump(progress_data, f, indent=4)
        with open(STATS_FILE, "w", encoding='utf-8') as f:
            json.dump(st.session_state.stats, f, indent=4)
        with open(COMBINED_BANK_FILE, "w", encoding='utf-8') as f:
            json.dump(st.session_state.all_questions, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"存档失败: {e}")


def load_all_data():
    if os.path.exists(COMBINED_BANK_FILE):
        try:
            with open(COMBINED_BANK_FILE, "r", encoding='utf-8') as f:
                st.session_state.all_questions = json.load(f)
        except:
            pass
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding='utf-8') as f:
                data = json.load(f)
                st.session_state.wrong_questions = set(data.get("wrong_questions", []))
                st.session_state.practice_index = data.get("practice_index", 0)
                st.session_state.wrong_index = data.get("wrong_index", 0)
                st.session_state.mode = data.get("mode", 'practice')
        except:
            pass
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r", encoding='utf-8') as f:
                st.session_state.stats = json.load(f)
        except:
            pass


def clear_local_data():
    for f in [HISTORY_FILE, STATS_FILE, COMBINED_BANK_FILE]:
        if os.path.exists(f): os.remove(f)
    st.session_state.all_questions = []
    st.session_state.wrong_questions = set()
    st.session_state.stats = {}
    st.session_state.practice_index = 0
    st.session_state.wrong_index = 0


# ================= 核心逻辑：Excel解析 (不动) =================

def find_header_row(df, possible_headers=['题目', '题干', '问题', 'Question']):
    for idx, row in df.head(10).iterrows():
        row_values = [str(val).strip() for val in row.values]
        if any(h in row_values for h in possible_headers): return idx
    return None


def standardize_columns(df):
    df.columns = [str(c).strip() for c in df.columns]
    col_mapping = {'题干': '题目', '问题': '题目', 'Question': '题目', '正确答案': '答案', 'Answer': '答案',
                   '解析': '解析', 'Analysis': '解析'}
    df.rename(columns=col_mapping, inplace=True)
    return df


# ================= 【核心修改】针对你的截图优化的 MD 解析器 =================

def parse_markdown_custom(content):
    """
    专门适配：
    **题目**: xxx
    **选项**:
    - xxx
    - xxx
    **答案**: A,B
    """
    questions = []
    # 按照 '## ' 或者 '##' 分割题目块
    blocks = re.split(r'(?:^|\n)##\s+', content)

    for block in blocks:
        if not block.strip(): continue

        q = {
            'question': '',
            'options': [],
            'answer': '',
            'analysis': '暂无解析',
            'type': '单选'
        }

        lines = block.strip().split('\n')
        current_section = None  # 标记当前在读哪个部分

        for line in lines:
            line = line.strip()
            if not line: continue

            # 1. 识别标题头 (兼容你的截图格式)
            if line.startswith('**题目**:') or line.startswith('**题目:**') or line.startswith('**Question**:'):
                current_section = 'question'
                # 提取冒号后面的内容
                parts = line.split(':', 1)
                if len(parts) > 1: q['question'] = parts[1].strip()
                continue

            if line.startswith('**选项**:') or line.startswith('**选项:**') or line.startswith('**Options**:'):
                current_section = 'options'
                continue

            if line.startswith('**答案**:') or line.startswith('**答案:**') or line.startswith('**Answer**:'):
                current_section = 'answer'
                parts = line.split(':', 1)
                if len(parts) > 1:
                    # 去掉空格，统一大写
                    q['answer'] = parts[1].strip().upper().replace(' ', '').replace('，', ',')
                continue

            if line.startswith('**解析**:') or line.startswith('**解析:**') or line.startswith('**Analysis**:'):
                current_section = 'analysis'
                parts = line.split(':', 1)
                if len(parts) > 1: q['analysis'] = parts[1].strip()
                continue

            # 2. 根据当前部分填充内容
            if current_section == 'question':
                # 如果是多行题目，追加
                q['question'] += ' ' + line

            elif current_section == 'options':
                # 识别列表符号 - 或 *
                if line.startswith('- ') or line.startswith('* '):
                    opt_text = line[2:].strip()
                    q['options'].append(opt_text)
                # 兼容已经带A.的情况
                elif re.match(r'^[A-F][\.,、]', line):
                    q['options'].append(line)

            elif current_section == 'analysis':
                q['analysis'] += '\n' + line

        # 3. 后处理：给选项加上 A. B. C.
        if q['options']:
            # 如果第一个选项不是以 A. 开头，说明是无序列表，需要自动编号
            if not re.match(r'^[A-F][\.,、]', q['options'][0]):
                lettered_opts = []
                for i, opt in enumerate(q['options']):
                    letter = chr(65 + i)  # 0->A, 1->B
                    lettered_opts.append(f"{letter}. {opt}")
                q['options'] = lettered_opts

        # 4. 存入结果
        if q['question'] and q['options'] and q['answer']:
            # 判断多选
            if ',' in q['answer'] or len(q['answer']) > 1:
                q['type'] = '多选'
            questions.append(q)

    return questions


def load_data_from_file(file_path_or_buffer, is_path=False):
    """读取数据主入口"""
    filename = file_path_or_buffer if is_path else file_path_or_buffer.name

    try:
        # === A. Markdown 处理 (调用新解析器) ===
        if filename.lower().endswith('.md'):
            if is_path:
                with open(file_path_or_buffer, 'r', encoding='utf-8') as f:
                    content = f.read()
            else:
                content = file_path_or_buffer.getvalue().decode('utf-8')

            md_questions = parse_markdown_custom(content)

            # 临时补全ID
            for idx, q in enumerate(md_questions): q['id'] = idx
            return md_questions

        # === B. Excel/CSV 处理 (不动) ===
        if is_path:
            if filename.endswith('.csv'):
                try:
                    df = pd.read_csv(file_path_or_buffer)
                except:
                    df = pd.read_csv(file_path_or_buffer, encoding='gbk')
            else:
                df = pd.read_excel(file_path_or_buffer)
        else:
            if filename.endswith('.csv'):
                try:
                    df = pd.read_csv(file_path_or_buffer)
                except:
                    file_path_or_buffer.seek(0)
                    df = pd.read_csv(file_path_or_buffer, encoding='gbk')
            else:
                df = pd.read_excel(file_path_or_buffer)

        if '题目' not in df.columns:
            header_idx = find_header_row(df)
            if header_idx is not None:
                if is_path:
                    if filename.endswith('.csv'):
                        try:
                            df = pd.read_csv(file_path_or_buffer, header=header_idx + 1)
                        except:
                            df = pd.read_csv(file_path_or_buffer, encoding='gbk', header=header_idx + 1)
                    else:
                        df = pd.read_excel(file_path_or_buffer, header=header_idx + 1)
                else:
                    file_path_or_buffer.seek(0)
                    if filename.endswith('.csv'):
                        try:
                            df = pd.read_csv(file_path_or_buffer, header=header_idx + 1)
                        except:
                            df = pd.read_csv(file_path_or_buffer, encoding='gbk', header=header_idx + 1)
                    else:
                        df = pd.read_excel(file_path_or_buffer, header=header_idx + 1)

        df = standardize_columns(df)
        if '题目' not in df.columns or '答案' not in df.columns: return []

        questions = []
        for idx, row in df.iterrows():
            if pd.isna(row['题目']): continue
            raw_ans = str(row['答案']).strip().upper().replace(',', '').replace('，', '').replace(' ', '').replace('.0',
                                                                                                                  '')
            q_type = '多选' if len(raw_ans) > 1 else '单选'
            options = []
            for tag in ['A', 'B', 'C', 'D', 'E', 'F']:
                col_candidates = [f'选项{tag}', f'{tag}', f'Option {tag}', f'Option{tag}']
                text = None
                for col in col_candidates:
                    if col in df.columns and pd.notna(row[col]):
                        text = row[col]
                        break
                if text: options.append(f"{tag}. {text}")

            if options:
                questions.append({
                    "id": idx,
                    "question": row['题目'],
                    "options": options,
                    "answer": raw_ans,
                    "type": q_type,
                    "analysis": row.get('解析', '暂无解析')
                })
        return questions
    except Exception as e:
        st.error(f"读取数据出错: {e}")
        return []


def check_answer(q_id, user_ans, correct_ans, threshold=1):
    # 清洗答案中的逗号，确保 A,B 和 AB 能匹配
    clean_user = user_ans.replace(',', '').replace(' ', '')
    clean_correct = correct_ans.replace(',', '').replace(' ', '')

    is_correct = sorted(clean_user) == sorted(clean_correct)

    q_id_str = str(q_id)
    if q_id_str not in st.session_state.stats:
        st.session_state.stats[q_id_str] = {'errors': 0, 'streak': 0}

    msg = ""
    if not is_correct:
        st.session_state.wrong_questions.add(q_id)
        st.session_state.stats[q_id_str]['errors'] += 1
        st.session_state.stats[q_id_str]['streak'] = 0
        msg = "❌ 回答错误，已加入错题本"
    else:
        st.session_state.stats[q_id_str]['streak'] += 1
        current_streak = st.session_state.stats[q_id_str]['streak']
        if q_id in st.session_state.wrong_questions:
            if current_streak >= threshold:
                st.session_state.wrong_questions.discard(q_id)
                msg = f"✅ 回答正确！连续答对 {current_streak} 次，已移出错题本"
            else:
                msg = f"✅ 回答正确！(连续答对 {current_streak}/{threshold} 次，继续加油)"
        else:
            msg = "✅ 回答正确"

    save_all_data()
    return is_correct, msg


# ================= 逻辑：启动时加载 =================
if not st.session_state.all_questions:
    load_all_data()

# ================= 界面构建 (不动) =================
with st.sidebar:
    st.header("📚 题库管理")
    uploaded_file = st.file_uploader("上传题库文件", type=["xlsx", "xls", "csv", "md"])

    col_up1, col_up2 = st.columns(2)
    with col_up1:
        if uploaded_file and st.button("🔴 覆盖旧题库"):
            data = load_data_from_file(uploaded_file)
            if data:
                clear_local_data()
                st.session_state.all_questions = data
                save_all_data()
                st.rerun()
    with col_up2:
        if uploaded_file and st.button("🟢 追加新题库"):
            new_data = load_data_from_file(uploaded_file)
            if new_data:
                current_max_id = len(st.session_state.all_questions)
                for i, q in enumerate(new_data):
                    q['id'] = current_max_id + i
                st.session_state.all_questions.extend(new_data)
                st.success(f"成功追加 {len(new_data)} 道题！")
                save_all_data()
                st.rerun()

    st.info(f"当前总题数: {len(st.session_state.all_questions)}")
    st.divider()

    # 模式选择
    if st.session_state.all_questions:
        mode = st.radio("模式", ["顺序刷题", "错题本复习"], index=0 if st.session_state.mode == 'practice' else 1)

        if mode == "错题本复习":
            st.session_state.mode = 'wrong'
            current_index_key = 'wrong_index'
            threshold = st.slider("🎯 错题移除门槛", 1, 5, 1)
            min_errors = st.slider("🔍 只看做错次数 >=", 0, 10, 0)
        else:
            st.session_state.mode = 'practice'
            current_index_key = 'practice_index'
            min_errors = 0

        if st.session_state.mode == 'practice':
            target_pool = st.session_state.all_questions
        else:
            target_pool = []
            for q in st.session_state.all_questions:
                if q['id'] in st.session_state.wrong_questions:
                    err_count = st.session_state.stats.get(str(q['id']), {}).get('errors', 0)
                    if err_count >= min_errors:
                        target_pool.append(q)
            st.info(f"错题剩余: {len(target_pool)} 道")

        if target_pool:
            curr = st.session_state[current_index_key]
            total = len(target_pool)
            if curr >= total: curr = 0
            st.progress((curr + 1) / total)
            st.caption(f"进度: {curr + 1} / {total}")

        st.divider()
        if st.button("🗑️ 清空进度 (保留题库)"):
            st.session_state.wrong_questions = set()
            st.session_state.stats = {}
            st.session_state.practice_index = 0
            st.session_state.wrong_index = 0
            save_all_data()
            st.rerun()

# ================= 主答题区 (不动) =================

if not st.session_state.all_questions:
    st.info("👈 请在左侧上传题库。")
else:
    if st.session_state.mode == 'practice':
        question_pool = st.session_state.all_questions
        current_index_key = 'practice_index'
    else:
        question_pool = []
        filter_val = min_errors if 'min_errors' in locals() else 0
        for q in st.session_state.all_questions:
            if q['id'] in st.session_state.wrong_questions:
                err_count = st.session_state.stats.get(str(q['id']), {}).get('errors', 0)
                if err_count >= filter_val:
                    question_pool.append(q)
        current_index_key = 'wrong_index'

    if not question_pool:
        if st.session_state.mode == 'wrong':
            st.balloons()
            st.success("🎉 恭喜！符合条件的错题已全部清空！")
        else:
            st.warning("⚠️ 题库数据异常")
    else:
        curr_idx = st.session_state[current_index_key]
        if curr_idx >= len(question_pool):
            curr_idx = 0
            st.session_state[current_index_key] = 0

        q = question_pool[curr_idx]
        q_stat = st.session_state.stats.get(str(q['id']), {'errors': 0, 'streak': 0})
        st.caption(f"📊 历史做错: {q_stat['errors']} 次 | 当前连对: {q_stat['streak']} 次")

        st.subheader(f"No.{curr_idx + 1}  {q['type']}")
        st.markdown(f"#### {q['question']}")

        with st.form(key=f"q_{q['id']}"):
            user_choice = []
            if q['type'] == '单选':
                val = st.radio("选择:", q['options'], index=None, key=f"radio_{q['id']}")
                if val: user_choice = val.split('.')[0]
            else:
                for opt in q['options']:
                    if st.checkbox(opt, key=f"chk_{q['id']}_{opt}"):
                        user_choice.append(opt.split('.')[0])

            col_sub1, col_sub2 = st.columns([1, 5])
            with col_sub1:
                submitted = st.form_submit_button("提交")

            if submitted:
                ans_str = "".join(sorted(user_choice))
                current_threshold = threshold if 'threshold' in locals() else 1
                ok, msg = check_answer(q['id'], ans_str, q['answer'], current_threshold)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)
                    st.info(f"**正确答案**: {q['answer']}")
                    st.markdown(f"> **解析**: {q['analysis']}")

        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("⬅️ 上一题"):
                if st.session_state[current_index_key] > 0:
                    st.session_state[current_index_key] -= 1
                    save_all_data()
                    st.rerun()
        with col2:
            if st.button("下一题 ➡️"):
                if st.session_state[current_index_key] < len(question_pool) - 1:
                    st.session_state[current_index_key] += 1
                    save_all_data()
                    st.rerun()