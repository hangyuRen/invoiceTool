import streamlit as st
import pdfplumber
import re
import pandas as pd
import io
import math
import uuid
import threading
import time
import os
from streamlit.web.server.server import Server

def clean_text(text):
    if not text: return ""
    return text.replace(' ', '').replace('　', '').replace('）', ')').replace('：', ':')

def re_text(bt, text):
    m1 = re.search(bt, text)
    if m1: return re_block(m1[0])
    return None
 
def re_block(text):
    return text.replace(' ', '').replace('　', '').replace('）', '').replace(')', '').replace('：', ':')

def extract_single_pdf(file_obj):
    """提取单个PDF信息"""
    data = {
        "filename": file_obj.name,
        "invoice_num": None,
        "seller_name": None,
        "amount": 0.0
    }
    try:
        with pdfplumber.open(file_obj) as pdf:
            if not pdf.pages: return data
            text = pdf.pages[0].extract_text()
            if not text: return data
            
            # A. 发票号码
            num_match = re.search(r'发\s*票\s*号\s*码\s*[:：]?\s*(\d{8,20})', text)
            if num_match: data['invoice_num'] = num_match.group(1)

            # B. 销售方名称
            name = re.findall(re.compile(r'名\s*称\s*[:： ]\s*([\u4e00-\u9fa5]+)'), text)
            if name:
                data['seller_name'] = name[1] if len(name) >= 2 else name[0]

            # C. 金额
            cost_match = re_text(re.compile(r'小写.*(.*[0-9.]+)'), text)
            if cost_match:
                try: data['amount'] = float(cost_match.replace("小写¥", ""))
                except: data['amount'] = 0.0
    except Exception as e:
        print(f"解析错误 {file_obj.name}: {e}")
    return data

def convert_df_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='发票汇总')
    return output.getvalue()


def auto_shutdown_monitor():
    while True:
        time.sleep(3)
        try:
            current_server = Server.get_current()
            if len(current_server._session_info_by_id) == 0:
                time.sleep(2)
                if len(Server.get_current()._session_info_by_id) == 0:
                    os._exit(0)
        except Exception:
            pass

# ==========================================
# 2. 前端页面
# ==========================================

def main():
    st.set_page_config(page_title="电子发票提取工具", layout="wide")

    if 'monitor_started' not in st.session_state:
        threading.Thread(target=auto_shutdown_monitor, daemon=True).start()
        st.session_state['monitor_started'] = True
        
    st.title("🧾 电子发票提取助手(PDF2Excel)")
    st.markdown("---")

    # === 初始化 Session State ===
    if 'df_result' not in st.session_state:
        st.session_state['df_result'] = pd.DataFrame(columns=["filename", "invoice_num", "seller_name", "amount", "报销人", "报销时间"])
    if 'current_page' not in st.session_state:
        st.session_state['current_page'] = 1
    if 'table_unique_key' not in st.session_state:
        st.session_state['table_unique_key'] = str(uuid.uuid4())
    if 'uploader_key' not in st.session_state:
        st.session_state['uploader_key'] = 0
    if 'last_uploaded_filenames' not in st.session_state:
        st.session_state['last_uploaded_filenames'] = set()
    
    # [新增] 初始化输入框的绑定变量
    if 'page_input_val' not in st.session_state:
        st.session_state['page_input_val'] = 1

    # === 回调函数定义区域 (核心修复) ===
    
    def clear_all_data():
        st.session_state['df_result'] = pd.DataFrame(columns=["filename", "invoice_num", "seller_name", "amount", "报销人", "报销时间"])
        st.session_state['last_uploaded_filenames'] = set()
        st.session_state['current_page'] = 1
        st.session_state['page_input_val'] = 1 # 同步重置输入框
        st.session_state['table_unique_key'] = str(uuid.uuid4())
        st.session_state['uploader_key'] += 1

    # [修复] 翻页时，必须同时更新 current_page 和 page_input_val
    def next_page():
        st.session_state['current_page'] += 1
        st.session_state['page_input_val'] = st.session_state['current_page']

    def prev_page():
        st.session_state['current_page'] -= 1
        st.session_state['page_input_val'] = st.session_state['current_page']

    # [修复] 手动输入数字时，同步更新 current_page
    def set_page():
        st.session_state['current_page'] = st.session_state['page_input_val']

    col_upload, col_preview = st.columns([1, 2.5])

    # --- 左侧：上传区域 ---
    with col_upload:
        st.subheader("📂 文件上传")
        
        uploaded_files = st.file_uploader(
            "请拖拽PDF发票文件到此处", 
            type=['pdf'], 
            accept_multiple_files=True,
            key=f"uploader_{st.session_state['uploader_key']}"
        )

        if not st.session_state['df_result'].empty or uploaded_files:
            st.button("🗑️ 一键清空所有数据", on_click=clear_all_data, type="secondary")

        # === 增量更新逻辑 ===
        if uploaded_files:
            current_files_map = {f.name: f for f in uploaded_files}
            current_filenames = set(current_files_map.keys())
            last_filenames = st.session_state['last_uploaded_filenames']

            deleted_files = last_filenames - current_filenames
            new_files = current_filenames - last_filenames

            if deleted_files or new_files:
                if deleted_files:
                    st.session_state['df_result'] = st.session_state['df_result'][
                        ~st.session_state['df_result']['filename'].isin(deleted_files)
                    ]
                
                if new_files:
                    new_data_list = []
                    progress_bar = st.progress(0)
                    for i, fname in enumerate(new_files):
                        file_obj = current_files_map[fname]
                        row = extract_single_pdf(file_obj)
                        row["报销人"] = ""
                        row["报销时间"] = ""
                        new_data_list.append(row)
                        progress_bar.progress((i + 1) / len(new_files))
                    
                    if new_data_list:
                        new_df = pd.DataFrame(new_data_list)
                        st.session_state['df_result'] = pd.concat([st.session_state['df_result'], new_df], ignore_index=True)

                st.session_state['last_uploaded_filenames'] = current_filenames
                st.session_state['table_unique_key'] = str(uuid.uuid4())
                st.rerun()

        elif not uploaded_files and st.session_state['last_uploaded_filenames']:
            clear_all_data()
            st.rerun()

        if uploaded_files:
            st.success(f"当前共有 {len(uploaded_files)} 个文件")
        else:
            st.info("等待上传文件...")

    # --- 右侧：预览与编辑区域 ---
    with col_preview:
        st.subheader("📝 数据预览与修正")
        
        df_master = st.session_state['df_result']

        if not df_master.empty:
            cols = ["报销人", "报销时间", "filename", "invoice_num", "seller_name", "amount"]
            rename_map = {'invoice_num': '发票号码', 'seller_name': '销售方名称', 'amount': '发票金额'}
            
            # 分页逻辑优化
            col_p1, col_p2 = st.columns([1, 3])
            with col_p1:
                page_size = st.selectbox("每页显示", [10, 20, 50, 100], index=0)
            
            total_rows = len(df_master)
            if total_rows > 0:
                total_pages = math.ceil(total_rows / page_size)
                
                # 安全检查与修正
                if st.session_state['current_page'] > total_pages: 
                    st.session_state['current_page'] = total_pages
                    st.session_state['page_input_val'] = total_pages # 同步修正输入框
                if st.session_state['current_page'] < 1: 
                    st.session_state['current_page'] = 1
                    st.session_state['page_input_val'] = 1 # 同步修正输入框
                
                with col_p2:
                    cp1, cp2, cp3 = st.columns([1, 2, 1])
                    
                    with cp1:
                        # 上一页
                        st.button("⬅️", 
                                 disabled=(st.session_state['current_page'] == 1), 
                                 on_click=prev_page) 
                    
                    with cp2:
                        # 页码输入框
                        # 关键点：value直接绑定key变量，这样回调修改key变量时，输入框才会变
                        st.number_input(
                            f"页码 / {total_pages}", 
                            min_value=1, 
                            max_value=total_pages, 
                            key="page_input_val", # 绑定到 session state 的这个 key
                            on_change=set_page,   # 手动输入时触发
                            label_visibility="collapsed"
                        )
                    
                    with cp3:
                        # 下一页
                        st.button("➡️", 
                                 disabled=(st.session_state['current_page'] == total_pages), 
                                 on_click=next_page)

                # 切片
                current_page = st.session_state['current_page']
                start_idx = (current_page - 1) * page_size
                end_idx = start_idx + page_size
                
                df_slice = df_master.iloc[start_idx:end_idx].copy()
                df_slice_renamed = df_slice.rename(columns=rename_map)
                display_cols = ["报销人", "报销时间", "发票号码", "销售方名称", "发票金额", "filename"]
                for c in display_cols:
                    if c not in df_slice_renamed.columns: df_slice_renamed[c] = ""
                
                # 编辑器
                edited_df = st.data_editor(
                    df_slice_renamed[display_cols],
                    use_container_width=True,
                    num_rows="fixed",
                    key=f"editor_{st.session_state['table_unique_key']}_{current_page}"
                )

                # 回写逻辑
                reverse_map = {v: k for k, v in rename_map.items()}
                edited_df_raw = edited_df.rename(columns=reverse_map)

                is_changed = False
                for idx, row in edited_df_raw.iterrows():
                    original_row = df_master.loc[idx]
                    for col in ["报销人", "报销时间", "invoice_num", "seller_name", "amount"]:
                        if original_row[col] != row[col]:
                            st.session_state['df_result'].at[idx, col] = row[col]
                            is_changed = True
                
                if is_changed:
                    st.rerun()

            st.markdown("---")

            # 下载
            df_download = st.session_state['df_result'].copy()
            df_download = df_download.rename(columns=rename_map)
            if 'filename' in df_download.columns:
                df_download = df_download.drop(columns=['filename'])
            
            final_cols = ["报销人", "报销时间", "发票号码", "销售方名称", "发票金额"]
            for c in final_cols:
                if c not in df_download.columns: df_download[c] = ""
            
            excel_data = convert_df_to_excel(df_download[final_cols])
            
            st.download_button(
                label="📥 保存并下载 Excel",
                data=excel_data,
                file_name="发票报销汇总.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
        else:
             st.write("👈 请先在左侧上传 PDF 文件")

if __name__ == "__main__":
    main()