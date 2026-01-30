import streamlit as st

st.set_page_config(page_title="TeachProxy Admin", layout="wide")

# Add project root to path for module imports
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

st.title("TeachProxy 教师管理面板")
st.write("请从左侧选择功能页面")
