'''
Author: hyuren
Date: 2026-01-28 14:19:11
LastEditTime: 2026-01-28 14:19:16
Description: 
'''
from PyInstaller.utils.hooks import copy_metadata, collect_data_files

# 收集 streamlit 的所有数据文件（包括前端网页文件）
datas = collect_data_files('streamlit')
# 复制元数据（版本号等）
datas += copy_metadata('streamlit')