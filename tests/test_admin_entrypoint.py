def test_admin_entrypoint_exists():
    assert open("admin/streamlit_app.py").read().strip() != ""
