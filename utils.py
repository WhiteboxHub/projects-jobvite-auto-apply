from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def upload_resume(driver, resume_path):
    """Uploads resume file"""
    try:
        file_input = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.NAME, "resume")))
        file_input.send_keys(resume_path)
    except Exception as e:
        print(f"Could not upload resume: {e}")

def fill_textbox(driver, field_name, value):
    """Fills a textbox field"""
    try:
        field = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.NAME, field_name)))
        field.clear()
        field.send_keys(value)
    except Exception as e:
        print(f"Could not fill {field_name}: {e}")

def select_dropdown(driver, field_name, value):
    """Selects an option from a dropdown"""
    try:
        dropdown = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.NAME, field_name)))
        dropdown.send_keys(value)
    except Exception as e:
        print(f"Could not select {field_name}: {e}")
