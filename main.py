import time
import json
import yaml
import logging
import os
import csv
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys

# logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logging.basicConfig(filename="system log.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

applied_jobs_file = "applied_jobs.yaml"
job_csv_file = "jobs/linkedin_jobs.csv"
BASE_URL = "https://jobs.jobvite.com"
csv_file = "config/answers.csv"

def get_logger():
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    date_str = datetime.now().strftime("%d-%m-%Y")
    log_filename = f"{date_str}.log"
    log_file_path = os.path.join(log_dir, log_filename)
    logger = logging.getLogger("JobStatusLogger")

    if not logger.handlers:
        logger.setLevel(logging.INFO)
        file_handler = logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
        formatter = logging.Formatter('%(message)s')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger

def logger_log_job_status(job_link, status):
    logger = get_logger()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = f"[{timestamp}], {status}, {job_link}"
    logger.info(log_entry)

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
    logger_log_job_status(job_link, status)

def generate_job_links(csv_filename):
    job_links = []

    try:
        with open(csv_filename, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                company = row.get("company", "").strip()
                job_id = row.get("job_id", "").strip()
                fallback_url = row.get("platform_link", "").strip()
                platform = row.get("platform", "").strip().lower()

                final_url = None

                if platform == "jobvite":
                    if company and job_id:
                        final_url = f"{BASE_URL}/{company}/job/{job_id}"
                    elif fallback_url:
                        final_url = fallback_url
                        logging.warning(f"Falling back to platform_link for row: {row}")
                    else:
                        logging.warning(f"Missing data to construct URL and no fallback: {row}")
                        continue

                    job_data = {
                        "company": company,
                        "job_id": job_id,
                        "url": final_url
                    }
                    job_links.append(job_data)
                else:
                    logging.info(f"Skipping non-Jobvite platform: {row}")

        logging.info(f"Loaded {len(job_links)} Jobvite job entries from {csv_filename}")

    except FileNotFoundError:
        logging.error(f"CSV file {csv_filename} not found.")
    except Exception as e:
        logging.exception(f"Unexpected error while reading {csv_filename}: {e}")

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

def read_csv(file_path):
    qa_dict = {}
    with open(file_path, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            question = row["question"].strip()
            answer = row["answer"].strip()
            qa_dict[question] = answer
    return qa_dict

def fill_form(driver, qa_data, filled_fields, filled_locators):
    completed_questions = set()

    for question, answer in qa_data.items():
        if question in filled_fields:
            logging.info(f"Skipping already filled question: {question}")
            continue

        try:
            label_xpath = f"//label[contains(normalize-space(), '{question}')] | //legend[contains(normalize-space(), '{question}')]"
            label_element = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, label_xpath))
            )

            radio_buttons = label_element.find_elements(By.XPATH, "following::input[@type='radio']")
            if radio_buttons:
                for rb in radio_buttons:
                    if rb.get_attribute("value").strip().lower() == answer.strip().lower():
                        driver.execute_script("arguments[0].click();", rb)
                        completed_questions.add(question)
                        filled_fields.add(question)
                        break
                continue

            input_element = None
            try:
                input_element = label_element.find_element(By.XPATH, "following::*[self::input or self::textarea or self::select][1]")
            except NoSuchElementException:
                continue

            if input_element:
                tag_name = input_element.tag_name.lower()
                if tag_name in ["input", "textarea"]:
                    if input_element.get_attribute("value").strip():
                        logging.info(f"Skipping already filled field: {question}")
                        filled_fields.add(question)
                        continue

                    input_element.clear()
                    input_element.send_keys(answer)

                elif tag_name == "select":
                    select = Select(input_element)
                    select.select_by_visible_text(answer)

                completed_questions.add(question)
                filled_fields.add(question)

        except Exception as e:
            logging.warning(f"Skipping question '{question}' - Element not found or error: {e}")

    if len(completed_questions) == len(qa_data):
        logging.info("------All questions have been filled. Stopping execution-----")


    filled_locators.update(filled_fields)

interacted_elements = set()

def interact_with_element(driver, css_selector, element_type, value=None, filled_locators=None):
    try:
        element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, css_selector))
        )

        if element in interacted_elements or (filled_locators and css_selector in filled_locators):
            return True

        existing_value = element.get_attribute("value")
        if existing_value:
            logging.info(f"Skipping already filled element: {css_selector}")
            if filled_locators is not None:
                filled_locators.add(css_selector)
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
        if filled_locators is not None:
            filled_locators.add(css_selector)
        return True

    except Exception as e:
        logging.error(f"Error interacting with element ({css_selector}): {e}")
        return False

def execute_automation(driver, locators, filled_locators):
    for key, locator in locators.items():
        interact_with_element(driver, locator["selector"], locator["type"], locator.get("value", ""), filled_locators)

def wait_until_all_required_filled(driver):
    while True:
        required_fields = driver.find_elements(By.CSS_SELECTOR, "input[required], select[required], textarea[required]")
        unfilled_fields = [field for field in required_fields if not field.get_attribute("value")]

        if not unfilled_fields:
            logging.info("All required fields are filled. Proceeding...")
            return

        for field in unfilled_fields:
            logging.info(f"Waiting for required field: {field.get_attribute('label') or field.get_attribute('id') or 'Unknown Field'}")

        time.sleep(5)

def handle_uninteracted_required_elements(driver, config, filled_locators):
    all_form_elements = driver.find_elements(By.CSS_SELECTOR, "input, select, textarea")
    for element in all_form_elements:
        if element not in interacted_elements:
            try:
                is_required = element.get_attribute("required") is not None
                if is_required and not element.get_attribute("value"):
                    element.clear()
                    element.send_keys(config.get(element.get_attribute("name"), ""))
                    interacted_elements.add(element)
                    if filled_locators is not None:
                        filled_locators.add(element.get_attribute("name"))
            except Exception as e:
                print(f"Error processing required element: {e}")

def upload_resume(driver, resume_path):
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
        logging.info("Clicked the Save button after pasting the resume.")

    except NoSuchElementException as e:
        logging.error(f"Element not found during resume upload: {e}")
    except Exception as e:
        logging.error(f"An error occurred: {e}")

def apply_to_job(driver, wait, job_id, job_link, resume_path, locators, config):
    logging.info(f"Opening job link: {job_link}")
    driver.get(job_link)

    filled_locators = set()  

    try:
        apply_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Apply') or contains(@class, 'apply-button')]")))
        apply_button.click()
        logging.info("Clicked Apply button.")
        time.sleep(5)

        filled_fields = set()

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

        upload_resume(driver, resume_path)

        execute_automation(driver, locators, filled_locators)
        handle_uninteracted_required_elements(driver, config, filled_locators)
        qa_data = read_csv(csv_file)
        fill_form(driver, qa_data, filled_fields, filled_locators)
        wait_until_all_required_filled(driver)

        next_button = wait.until(EC.element_to_be_clickable((
        By.CSS_SELECTOR, "button.jv-button.jv-button-primary.jv-button-large"
        )))
        next_button.click()
        logging.info("------Clicked Next button----")
        time.sleep(5)

        execute_automation(driver, locators, filled_locators)
        handle_uninteracted_required_elements(driver, config, filled_locators)
        qa_data = read_csv(csv_file)
        fill_form(driver, qa_data, filled_fields, filled_locators)
        wait_until_all_required_filled(driver)

        try:
            next_button = wait.until(EC.element_to_be_clickable((
            By.CSS_SELECTOR, "button.jv-button.jv-button-primary.jv-button-large"
            )))
            next_button.click()
            logging.info("-----Clicked the Next button proceeding to the next page-----")
            time.sleep(5)
            print("---- Clicked the Next button proceeding to the next page-------")

            execute_automation(driver, locators, filled_locators)
            handle_uninteracted_required_elements(driver, config, filled_locators)
            qa_data = read_csv(csv_file)
            fill_form(driver, qa_data, filled_fields, filled_locators)
            wait_until_all_required_filled(driver)

        except:
            send_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'jv-button-primary') and contains(., 'Send Application')]")))
            driver.execute_script("arguments[0].click();", send_button)
            print("No Next button found, clicked Send Application.")
            # time.sleep(20)

        send_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'jv-button-primary') and contains(., 'Send Application')]")))
        driver.execute_script("arguments[0].click();", send_button)
        logging.info("------Clicked 'Send Application' button-------")
        # time.sleep(20)

        try:
            confirmation_message = wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR, "h2.jv-page-message-header"
            )))
            print("---------------------Applied_Successfully----------------------------------------")
            logging.info("Application submitted successfully!")
            log_job_status(job_link, "Successfully Applied")

        except TimeoutException:
            try:
                already_applied_message = wait.until(EC.presence_of_element_located((
                By.CSS_SELECTOR, "p.jv-page-error-header"
                )))
                print("---------------------------already_applied----------------------------------------")
                logging.info("-----You have already submitted the application------")
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

def list_user_configs():
    config_dir = "credentials"
    config_files = [f for f in os.listdir(config_dir) if f.endswith('.yaml')]
    if not config_files:
        logging.error("No user configuration files found.")
        exit(1)

    print("Available user configurations:")
    for idx, config_file in enumerate(config_files, start=1):
        print(f"{idx}. {config_file}")

    return config_files

def select_user_config(config_files):
    try:
        choice = int(input("Select a user configuration by number: "))
        if 1 <= choice <= len(config_files):
            return config_files[choice - 1]
        else:
            logging.error("Invalid selection.")
            exit(1)
    except ValueError:
        logging.error("Invalid input. Please enter a number.")
        exit(1)

def main():
    config_files = list_user_configs()
    selected_config = select_user_config(config_files)
    config_path = os.path.join("credentials", selected_config)

    with open(config_path, "r") as file:
        config = yaml.safe_load(file)


    resume_filename = config.get("resume_file", selected_config.replace('.yaml', '.txt'))
    resume_path = os.path.join("resume", resume_filename)

    if not os.path.isfile(resume_path):
        logging.error(f"Resume file not found at {resume_path}")
        exit(1)

    with open("locators/jobvite_locators.json", "r") as f:
        locators = json.load(f)

    for key in locators.keys():
        if key in config:
            locators[key]["value"] = config[key]

    for key, locator in locators.items():
        placeholder = f"{{{{ {key.replace('_', ' ')} }}}}"
        if locator.get("value") == placeholder:
            locator["value"] = config.get(key.replace("_", " "), "")

    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    wait = WebDriverWait(driver, 20)

    applied_jobs = load_applied_jobs()
    job_links = generate_job_links(job_csv_file)

    for job in job_links:
        job_id = job["job_id"]
        job_link = job["url"]

        if job_link in applied_jobs and applied_jobs[job_link] == "Successfully Applied":
            logging.info(f"Skipping already applied job: {job_id}")
            continue

        apply_to_job(driver, wait, job_id, job_link, resume_path, locators, config)

    driver.quit()

if __name__ == "__main__":
    main()
