import streamlit as st
import pandas as pd
import uuid
import hashlib
from datetime import datetime
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

st.header("👥 学生管理")

try:
    from admin.db_utils import get_all_students, get_db_session
    from gateway.app.db.models import Student
    
    # Add new student form
    with st.expander("➕ 添加新学生", expanded=False):
        with st.form("add_student_form"):
            name = st.text_input("姓名")
            email = st.text_input("邮箱")
            quota = st.number_input("周额度 (Tokens)", min_value=0, value=10000, step=1000)
            submitted = st.form_submit_button("添加学生")
            
            if submitted and name and email:
                session = get_db_session()
                try:
                    # Generate API key
                    api_key = f"sk-{uuid.uuid4().hex[:24]}"
                    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
                    
                    new_student = Student(
                        id=str(uuid.uuid4()),
                        name=name,
                        email=email,
                        api_key_hash=api_key_hash,
                        created_at=datetime.now(),
                        current_week_quota=quota,
                        used_quota=0
                    )
                    session.add(new_student)
                    session.commit()
                    st.success(f"✅ 学生 {name} 添加成功！")
                    st.code(f"API Key: {api_key}", language="text")
                    st.warning("⚠️ 请复制保存此 API Key，它只会显示一次！")
                except Exception as e:
                    session.rollback()
                    st.error(f"添加失败: {e}")
                finally:
                    session.close()
    
    st.divider()
    
    # Display students list
    students = get_all_students()
    
    if students:
        data = [{
            "ID": s.id[:8] + "...",
            "姓名": s.name,
            "邮箱": s.email,
            "周额度": s.current_week_quota,
            "已使用": s.used_quota,
            "剩余": max(0, s.current_week_quota - s.used_quota),
            "创建时间": s.created_at.strftime("%Y-%m-%d") if s.created_at else "-"
        } for s in students]
        
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(f"共 {len(students)} 名学生")
    else:
        st.info("暂无学生数据，请先添加学生")

except ImportError as e:
    st.warning(f"模块加载失败: {e}")
except Exception as e:
    st.error(f"加载学生数据失败: {e}")
