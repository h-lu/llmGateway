def test_readme_has_run_commands():
    text = open("README.md").read()
    assert "uvicorn gateway.app.main:app" in text
    assert "streamlit run admin/streamlit_app.py" in text
