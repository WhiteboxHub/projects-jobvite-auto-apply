import pyautogui
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
job_csv_file = "jobs\linkedin_jobs.csv"
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
    "country_select": {"selector": "#jv-country-select", "type": "select", "value": "c3a38d35-2bc8-40af-af8e-02457a174c32"},
    "first_name": {"selector": "#jv-field-yiYcYfwa", "type": "input", "value":  config["first_name"]},
    "last_name": {"selector": "#jv-field-yhYcYfw9", "type": "input", "value": config["last_name"]},
    "email": {"selector": "#jv-field-ygYcYfw8", "type": "input", "value": config["email"]},
    "phone": {"selector": "#jv-field-yjYcYfwb", "type": "input", "value": config["phone"]},
    "work_status": {"selector": "#jv-field-ymIyZfwl", "type": "select", "value": config["work_status"]},
    "work_authorization": {"selector": "#jv-field-yUfzZfwr", "type": "select", "value": config["work_authorization"]},
    "gender": {"selector": "#jv-form-field-legend ng-binding", "type": "radio", "value": config["gender"]},
    
}


interacted_elements = set()

def interact_with_element(driver, css_selector, element_type, value=None):
    
    try:
       
        element = WebDriverWait(driver, 0).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, css_selector))
        )

       
        if element_type == "input":
            
            if value:
                element.clear()
                element.send_keys(value)
            else:
              
                field_name = None
                if "autocomplete" in element.attrs:
                    field_name = element.get_attribute("autocomplete").lower().replace(" ", "_")
                elif "name" in element.attrs:
                    field_name = element.get_attribute("name").lower().replace(" ", "_")
                elif "id" in element.attrs:
                    field_name = element.get_attribute("id").lower().replace(" ", "_")

                if field_name:
                    print(f"Extracted field name: --------------------------------------{field_name}-------------")  
                    value_from_config = config.get(field_name)  
                    if value_from_config:
                        element.clear()
                        element.send_keys(value_from_config)
                    else:
                        print(f"No value found in config for {field_name}, sending default text.")
                        element.clear()
                        element.send_keys("AutoFilled") 
                else:
                    print("Field name not found in element attributes, cannot determine field name.")
                    element.clear()
                    element.send_keys("AutoFilled")

     
        elif element_type == "button":
            element.click()

      
        elif element_type == "select":
            select = Select(element)
            select.select_by_visible_text(value or select.options[1].text) 

      
        elif element_type in ["radio", "checkbox"]:
            if not element.is_selected():
                element.click()

     
        elif element_type == "textarea":
            element.clear()
            element.send_keys(value or "Sample text")

        else:
            print(f"Unsupported element type: {element_type}")
            return False

       
        interacted_elements.add(element)
        return True

    except Exception as e:
        print(f"Error interacting with element ({css_selector}): {e}")
        return False

        
def execute_automation(driver):
    """ Loops through locators and interacts with them. """
    for key, locator in locators.items():
        print(f"---------------------------{locator}----------------------------")
        css_selector = locator["selector"]
        print(f"---------------------------{css_selector}----------------------------")

        element_type = locator["type"]
        print(f"---------------------------{element_type}----------------------------")

        value = locator.get("value", "")
        print(f"Interacting with: {key}")
        interact_with_element(driver, css_selector, element_type,value)



def handle_uninteracted_required_elements(driver, config):

    all_form_elements = driver.find_elements(By.CSS_SELECTOR, "input, select, textarea")
    for element in all_form_elements:
        if element not in interacted_elements: 
            try:
                is_required = element.get_attribute("required") is not None
                if is_required:
                    tag_name = element.tag_name.lower()
                    element_type = element.get_attribute("type") or ""
                    print(f"Processing {tag_name} -----------------------------element with required={is_required}") 

                    if tag_name == "input":
                        field_name = element.get_attribute("placeholder")
                        if field_name:  
                            print(f"Placeholder: ---------------------{field_name}") 
                        else:
                            field_name = "default_field_name"
                            print(f"Field has no placeholder. Using default name: ---------------------{field_name}")  

                        field_name_transformed = field_name.replace(" ", "_").lower()
                        print(f"Transformed field name:-------------------- {field_name_transformed}")  

                        value_from_config = config.get(field_name_transformed)
                        if value_from_config:
                            print(f"Filling {field_name} with ---------------------{value_from_config}------------")  
                            element.send_keys(value_from_config)  
                        else:
                            print(f"No config value for {field_name}. ---------------Using fallback-----------------")  
                            element.send_keys("AutoFilled") 

                    elif tag_name == "textarea":
                        element.send_keys("AutoFilled Text")
                    elif tag_name == "select":
                        select = Select(element)
                        select.select_by_index(1)

                    print(f"Auto-filled required element: -------------------{element.get_attribute('outerHTML')}")
            except Exception as e:
                print(f"Error processing required element:-------------------- {e}----------")


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

        time.sleep(10)

        textarea = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "#jv-paste-resume-textarea0"))
        )
        textarea.clear()  
        textarea.send_keys(resume_text)  
        logging.info("Pasted resume text into the textarea.")

        time.sleep(1)

        save_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.jv-button.jv-button-primary[ng-disabled='!pastedText']"))
        )

        save_button.click()
        logging.info("Clicked the 'Save' button after pasting the resume.")

        time.sleep(5)
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
                
        execute_automation(driver)
        handle_uninteracted_required_elements(driver, config)

        select_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Select')]")))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", select_button)
        time.sleep(1)



        try:
            select_button.click()
            logging.info("Clicked Select button for resume upload.")

        except Exception as e:
            logging.warning(f"Click intercepted. Trying JavaScript click instead. Error: {e}")
            driver.execute_script("arguments[0].click();", select_button)

            
        time.sleep(5)

        upload_resume(driver, resume_text)

        execute_automation(driver)
        handle_uninteracted_required_elements(driver, config)

    
        next_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Next')]")))
        next_button.click()
        time.sleep(20)
        logging.info("Next Button Clicked  successfully!")

        execute_automation(driver)
        handle_uninteracted_required_elements(driver, config)



        send_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'jv-button-primary') and contains(., 'Send Application')]")))
        
        driver.execute_script("arguments[0].click();", send_button)
        logging.info("Clicked 'Send Application' button.")
        try:
            confirmation_message = wait.until(EC.presence_of_element_located(
                (By.XPATH, "//div[contains(text(), 'Your application has been submitted')]")
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
