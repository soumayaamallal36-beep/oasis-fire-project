@echo off
cd /d C:\Users\hp\Desktop\oasis_fire_project
call venv\Scripts\activate
python -m streamlit run dashboard/Home.py
pause