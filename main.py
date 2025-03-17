import time
import yaml
import logging
import os
import csv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

with open("job_application_config.yaml", "r") as file:
    config = yaml.safe_load(file)

applied_jobs_file = "applied_jobs.yaml"
job_csv_file = "jobs/linkedin_jobs.csv"
BASE_URL = "https://jobs.jobvite.com"

def load_applied_jobs():
    if os.path.exists(applied_jobs_file):
        with open(applied_jobs_file, "r") as file:
            return yaml.safe_load(file) or {}
    return {}

def save_applied_jobs(data):
    with open(applied_jobs_file, "w") as file:
        yaml.dump(data, file)

def log_job_status(job_link, status):
    jobs_data = load_applied_jobs()
    jobs_data[job_link] = status
    save_applied_jobs(jobs_data)

def generate_job_links(csv_filename):
    job_links = []
    try:
        with open(csv_filename, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                platform = row.get("platform", "").strip().lower()
                relative_url = row.get("url", "").strip()
                job_id = row.get("jobid", "").strip()

                if platform == "jobvite" and relative_url.startswith("/"):
                    full_url = f"{BASE_URL}{relative_url}"
                    job_links.append((job_id, full_url))
                else:
                    logging.warning(f"Skipping invalid row: {row}")

    except FileNotFoundError:
        logging.error(f"CSV file {csv_filename} not found.")

    return job_links

def load_jobs():
    job_links = "jobs/linkedin_jobs.csv"
    jobvite_links = []

    if os.path.exists(job_links):
        with open(job_links, "r") as file:
            reader = csv.reader(file)
            next(reader)
            for row in reader:
                if row and len(row) > 0:
                    link = row[0]
                    if "jobvite" in link.lower():
                        jobvite_links.append(link)
                else:
                    logging.warning(f"Skipping empty or malformed row: {row}")

    return jobvite_links

locators = {
    # "country_select": {"selector": "select#jv-country-select", "type": "select", "value": "c3a38d35-2bc8-40af-af8e-02457a174c32"},
    "first_name": {"selector": "input[autocomplete='given-name'][type='text'][maxlength='100']", "type": "input", "value": config["first_name"]},
    "last_name": {"selector": "input[autocomplete='family-name'][type='text'][maxlength='100']", "type": "input", "value": config["last_name"]},
    "email": {"selector": "input[autocomplete='email'][type='text']", "type": "input", "value": config["email"]},
    "phone": {"selector": "input[autocomplete='tel'][type='tel']", "type": "input", "value": config["phone"]},
    "address": {"selector": "input[autocomplete='address-line1'][type='text'][maxlength='100']", "type": "input", "value": config["address"]},

    "city": {"selector": "input[autocomplete='address-level2'][type='text'][maxlength='100']", "type": "input", "value": config["city"]},
    "state": {"selector": "select[autocomplete='address-level1']", "type": "select", "value": config["state"]},
    "zip": {"selector": "input[autocomplete='postal-code'][type='text'][maxlength='100']", "type": "input", "value": config["zip"]},
   
    "country": {"selector": "select[autocomplete='country-name'][required]", "type": "select", "value": config["country"]},
    "visa_status": { "selector": "select[id^='jv-field-'][name^='input-'][autocomplete='on'][required]", "type": "select", "value": config["visa_status"] },

    "work_authorization": {"selector": "select[id^='jv-field-'][name^='input-'][autocomplete='on'][required]", "type": "select", "value": config["work_authorization"]},
    "gender": { "selector": "select[autocomplete='on'][aria-required='false'][ng-required='field.required']", "type": "select", "value": config["gender"] },
    # "gender_radio": { "selector": "input[type='radio'][name='gender']", "type": "radio", "value": config["gender"]},
    # "referred": {"selector": "input[autocomplete='on'][required]", "type": "text", "value": config["referred"]},
    #"gender": {"selector": "input[type='radio'][id*='gender'][value='Male']", "type": "radio", "value": config["gender"]},
}

interacted_elements = set()

def interact_with_element(driver, css_selector, element_type, value=None):
    try:
        element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, css_selector))
        )

        if element in interacted_elements:
            return True 

        if element_type == "input":
            element.clear()
            element.send_keys(value or "")

        elif element_type == "select":
            select = Select(element)
            try:
                select.select_by_value(value)
            except:
                select.select_by_visible_text(value)

        elif element_type in ["radio", "checkbox"] and not element.is_selected():
            element.click()

        elif element_type == "textarea":
            element.clear()
            element.send_keys(value)

        elif element_type == "button":
            element.click()

        interacted_elements.add(element)  
        return True

    except Exception as e:
        logging.error(f"Error interacting with element ({css_selector}): {e}")
        return False

def execute_automation(driver):
    for key, locator in locators.items():
        interact_with_element(driver, locator["selector"], locator["type"], locator.get("value", ""))

def wait_until_all_required_filled(driver):
    while True:
        missing_fields = []
        all_form_elements = driver.find_elements(By.XPATH, "//input | //select | //textarea")

        for element in all_form_elements:
            if element in interacted_elements:
                continue  

            if element.get_attribute("required") is not None:
                if element.get_attribute("value") in [None, ""]:
                    missing_fields.append(element)

        if not missing_fields:
            break

        logging.info(f"Waiting for {len(missing_fields)} required fields to be filled...")
        time.sleep(5)



def handle_uninteracted_required_elements(driver, config):
    all_form_elements = driver.find_elements(By.CSS_SELECTOR, "input, select, textarea")
    for element in all_form_elements:
        if element not in interacted_elements:
            try:
                is_required = element.get_attribute("required") is not None
                if is_required and not element.get_attribute("value"):
                    element.clear()
                    element.send_keys(config.get(element.get_attribute("name"), ""))
                    interacted_elements.add(element)
            except Exception as e:
                print(f"Error processing required element: {e}")

resume_text = "resume/resume.txt"
resume_path = os.path.abspath(resume_text)

if not os.path.isfile(resume_path):
    logging.error(f"Resume file not found at {resume_path}")
    exit(1)

options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)
wait = WebDriverWait(driver, 20)

def upload_resume(driver, resume_text):
    try:
        with open(resume_path, 'r') as file:
            resume_text = file.read()

        paste_resume_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "span.jv-text-block.jv-text-link.needsclick.ng-binding"))
        )
        paste_resume_button.click()
        logging.info("Selected 'Type or Paste Resume' option.")


        textarea = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "#jv-paste-resume-textarea0"))
        )
        textarea.clear()
        textarea.send_keys(resume_text)
        logging.info("Pasted resume text into the textarea.")


        save_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.jv-button.jv-button-primary[ng-disabled='!pastedText']"))
        )
        save_button.click()
        logging.info("Clicked the 'Save' button after pasting the resume.")

    except NoSuchElementException as e:
        logging.error(f"Element not found during resume upload: {e}")
    except Exception as e:
        logging.error(f"An error occurred: {e}")

def apply_to_job(job_id, job_link):
    logging.info(f"Opening job link: {job_link}")
    driver.get(job_link)

    try:
        apply_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Apply') or contains(@class, 'apply-button')]")))
        apply_button.click()
        logging.info("Clicked Apply button.")
        time.sleep(5)


        elements = driver.find_elements(By.XPATH, '//*[@required="required"]')

       
        for element in elements:
            element_id = element.get_attribute("id")
            element_value = element.get_attribute("value") or element.get_attribute("name")
            autocomplete_attr = element.get_attribute("autocomplete")
            
            print(f"ID: {element_id}, Value: {element_value}, Autocomplete: {autocomplete_attr}")


            label = None
            for i in range(1, 6):
                label_xpath = f'./ancestor::*[{i}]/label'
                label_element = element.find_elements(By.XPATH, label_xpath)
                if label_element:
                    label = label_element[0].text
                    break  

            
            label_text = label if label else "No label found"
            
            print(f"ID: {element_id}, Value: {element_value}, Nearest Label: {label_text}")


        select_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Select')]")))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", select_button)
        time.sleep(1)

        try:
            select_button.click()
            logging.info("Clicked Select button for resume upload.")
        except Exception as e:
            logging.warning(f"Click intercepted. Trying JavaScript click instead. Error: {e}")
            driver.execute_script("arguments[0].click();", select_button)

        time.sleep(2)

        upload_resume(driver, resume_text)

        execute_automation(driver)
        handle_uninteracted_required_elements(driver, config)
        wait_until_all_required_filled(driver)

        next_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Next')]")))
        next_button.click()

        logging.info("Next Button Clicked successfully!")
        time.sleep(5)


        execute_automation(driver)
        handle_uninteracted_required_elements(driver, config)
        wait_until_all_required_filled(driver)

        send_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'jv-button-primary') and contains(., 'Send Application')]")))
        driver.execute_script("arguments[0].click();", send_button)
        logging.info("Clicked 'Send Application' button.")


        try:
            confirmation_message = wait.until(EC.presence_of_element_located(
                (By.XPATH, "//div[contains(text(), 'Application Sent!')]")
            ))
            logging.info("Application submitted successfully!")
            log_job_status(job_link, "Successfully Applied")

        except TimeoutException:
            try:
                already_applied_message = wait.until(EC.presence_of_element_located(
                    (By.XPATH, "//div[contains(text(), 'already applied')] | //div[contains(text(), \"You've already applied!\")]")
                ))
                logging.info("You have already submitted the application.")
                log_job_status(job_link, "Already Applied")
            except TimeoutException:
                logging.error("Unable to submit the application and no confirmation message found.")
                log_job_status(job_link, "Submission Failed")

    except TimeoutException:
        logging.error(f"Timeout: Could not find elements for job {job_link}")
        log_job_status(job_link, "Failed")
    except NoSuchElementException as e:
        logging.error(f"Error applying for job: {e}")
        log_job_status(job_link, "Failed")

def main():
    applied_jobs = load_applied_jobs()
    job_links = generate_job_links(job_csv_file)

    for job_id, job_link in job_links:
        if job_link in applied_jobs and applied_jobs[job_link] == "Successfully Applied":
            logging.info(f"Skipping already applied job: {job_id}")
            continue
        apply_to_job(job_id, job_link)

    driver.quit()

if __name__ == "__main__":
    main()
