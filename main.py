import re
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

logging.basicConfig(filename = "system log.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
# log_file = logging.FileHandler("./logger.log")
# mylogging = logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
# logging= logging.Handler(log_file)
# x = logging.getLogger("LOG INFO")
# x.

with open("job_application_config.yaml", "r") as file:
    config = yaml.safe_load(file)

applied_jobs_file = "applied_jobs.yaml"
job_csv_file = "jobs/linkedin_jobs.csv"
BASE_URL = "https://jobs.jobvite.com"


LABEL_MAPPINGS = {
    "first name": ["legal first name", "first name", "your name" "preferred first name"],
    "last name": ["legal last name", "last name", "preferred last name"],
    "email": ["email", "email address"],
    "phone": ["cell phone", "mobile phone", "phone", "phone number"],
    "work experience": ["how many years of professional experience do you have relevant to the position to which you are applying excluding internships" , "how many years of professional managerial experience do you have relevant to the position to which you are applying excluding internships you may skip if applying to an individual contributor position"],
    "work status": ["visa status", "work status"],
    "degree": ["highest level of degree you are pursuing or achieved"],
    "college/university":["Select the College/University Attended","select the collegeuniversity attended"],
    "work authorization": ["work authorization"],
    "how did you hear about this job" : ["How did you hear about this Job?"],

}

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
    except FileNotFoundError:
        logging.error(f"CSV file {csv_filename} not found.")
    return job_links



options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)
wait = WebDriverWait(driver, 20)


def normalize_label(label):
    if label:
        return re.sub(r"[^a-zA-Z0-9 ]", "", label).strip().lower()
    return ""


def map_label_to_config(label):
    normalized_label = normalize_label(label)
    print(f"normalized label------------------------------------------ {normalized_label}")
    for key, variations in LABEL_MAPPINGS.items():
        if normalized_label in variations:
            return key
    return normalized_label  


def interact_with_element(element, value):
    try:
        tag_name = element.tag_name.lower()
        if tag_name == "input":
            element.clear()
            element.send_keys(value)
        elif tag_name == "select":
            select = Select(element)
            try:
                select.select_by_value(value)
            except:
                select.select_by_visible_text(value)
        elif tag_name == "textarea":
            element.clear()
            element.send_keys(value)
        elif tag_name in ["radio", "checkbox"] and not element.is_selected():
            element.click()
        return True
    except Exception as e:
        logging.error(f"Error interacting with element: {e}")
        return False



#
def fill_form_fields(driver, config):
    elements = driver.find_elements(By.CSS_SELECTOR, "input, select, textarea")
    for element in elements:
        label = None
        for i in range(1, 6):
            label_xpath = f'./ancestor::*[{i}]/label'
            label_element = element.find_elements(By.XPATH, label_xpath)
            if label_element:
                label = label_element[0].text.strip()
                break
        
        if label:
            mapped_label = map_label_to_config(label)
            if mapped_label in config:
                value = config[mapped_label]
                interact_with_element(element, value)
                logging.info(f"Filled field '{label}' with '{value}'")
            else:
                logging.warning(f"No matching value found for label: {label}")


def wait_until_all_required_filled(driver):
    """Waits indefinitely until all required fields are filled, checking every 5 seconds."""
    while True:
        required_fields = driver.find_elements(By.CSS_SELECTOR, "input[required], select[required], textarea[required]")
        unfilled_fields = [field for field in required_fields if not field.get_attribute("value")]

        if not unfilled_fields:
            logging.info("All required fields are filled. Proceeding...")
            return 

        for field in unfilled_fields:
            logging.info(f"Waiting for required field: {field.get_attribute('label') or field.get_attribute('id') or 'Unknown Field'}")

        time.sleep(5)


resume_text = "resume/resume.txt"
resume_path = os.path.abspath(resume_text)

if not os.path.isfile(resume_path):
    logging.error(f"Resume file not found at {resume_path}")
    exit(1)


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
        apply_button = wait.until(EC.element_to_be_clickable((
        By.CSS_SELECTOR, "a.jv-button.jv-button-primary.jv-button-apply"
        )))
        apply_button.click()
        logging.info("Clicked Apply button")
        time.sleep(5)


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


        fill_form_fields(driver, config)
        wait_until_all_required_filled(driver)
        time.sleep(5)

    
       
        next_button = wait.until(EC.element_to_be_clickable((
        By.CSS_SELECTOR, "button.jv-button.jv-button-primary.jv-button-large"
        )))
        next_button.click()
        logging.info("Clicked Next button")
        time.sleep(5)

        fill_form_fields(driver, config)
        wait_until_all_required_filled(driver)


        try:
            next_button = wait.until(EC.element_to_be_clickable((
            By.CSS_SELECTOR, "button.jv-button.jv-button-primary.jv-button-large"
            )))
            next_button.click()
            logging.info("Clicked Next button")
            time.sleep(5)
            print("Clicked the Next button, proceeding to the next page.")

        except:
            send_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'jv-button-primary') and contains(., 'Send Application')]")))
            driver.execute_script("arguments[0].click();", send_button)
            print("No Next button found, clicked Send Application.")

            # send_button = wait.until(EC.element_to_be_clickable((
            # By.CSS_SELECTOR, "button.jv-button.jv-button-primary"
            # )))
            # send_button.click()
            # logging.info("✅ Clicked 'Send Application' button.")
            # time.sleep(5)

            # send_button = wait.until(EC.presence_of_element_located((
            # By.CSS_SELECTOR, "button.jv-button.jv-button-primary"
            # )))
            # driver.execute_script("arguments[0].click();", send_button)
            # logging.info("✅ Clicked 'Send Application' button using JavaScript.")
            # time.sleep(5)

        
        fill_form_fields(driver, config)
        wait_until_all_required_filled(driver)

        send_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'jv-button-primary') and contains(., 'Send Application')]")))
        driver.execute_script("arguments[0].click();", send_button)

        # send_button = wait.until(EC.element_to_be_clickable((
        # By.CSS_SELECTOR, "button.jv-button.jv-button-primary"
        # )))
        # send_button.click()
        # logging.info("✅ Clicked 'Send Application' button.")
        # time.sleep(5)


        # send_button = wait.until(EC.presence_of_element_located((
        # By.CSS_SELECTOR, "button.jv-button.jv-button-primary"
        # )))
        # driver.execute_script("arguments[0].click();", send_button)
        # logging.info("✅ Clicked 'Send Application' button using JavaScript.")
        # time.sleep(5)


        try:
            confirmation_message = wait.until(EC.presence_of_element_located((
                By.XPATH, "//div[contains(text(), 'Application Sent!') or contains(text(), 'Application Submitted!')]"
            )))
            print("*-*--*--*--*-----*--*-**-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*--*-*-*-*-*----*-*---*-*-*-*-*")
            logging.info("Application submitted successfully!")
            log_job_status(job_link, "Successfully Applied")

        except TimeoutException:
            try:
                already_applied_message = wait.until(EC.presence_of_element_located((
                    By.XPATH, "//p[contains(@class, 'jv-page-error-header') and contains(text(), \"You've already applied!\")]"
                )))
                print("---------------------------already_applied----------------------------------------")
                logging.info("You have already submitted the application.")
                log_job_status(job_link, "Already Submitted")

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
