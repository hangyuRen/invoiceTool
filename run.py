'''
Author: hyuren
Date: 2026-01-28 13:57:26
LastEditTime: 2026-01-28 15:33:22
Description: 
'''
import streamlit.web.cli as stcli
import os, sys
import webbrowser
from threading import Timer

def resolve_path(path):
    """获取资源绝对路径"""
    if getattr(sys, 'frozen', False):
        basedir = sys._MEIPASS
    else:
        basedir = os.path.dirname(__file__)
    return os.path.join(basedir, path)

def open_browser():
    """延迟 0.5 秒后自动打开浏览器"""
    # 这里默认是 8501 端口，如果你改了端口，这里也要改
    webbrowser.open_new("http://localhost:8501")

if __name__ == "__main__":
    # 构造启动命令
    sys.argv = [
        "streamlit",
        "run",
        resolve_path("app.py"),
        "--global.developmentMode=false"
    ]
    
    # 【关键修改】设置定时器，1.5秒后调用 open_browser 函数
    # 这样可以在 Streamlit 服务器启动成功后，正好打开网页
    Timer(0.5, open_browser).start()
    
    # 启动 Streamlit
    sys.exit(stcli.main())