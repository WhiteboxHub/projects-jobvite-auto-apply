import pyautogui
import time
import yaml
import logging
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)
    

with open("config.yaml", "r") as file:
    resume_data = yaml.safe_load(file)

resume_file = resume_data.get("resume_file", "resume/Sunil.pdf")


resume_path = os.path.abspath(resume_file) 

if not os.path.isfile(resume_path):
    logging.error(f"Resume file not found at {resume_path}")
    exit(1)  


options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)
wait = WebDriverWait(driver, 20)


def fill_textbox(driver, label_text, value):
    try:
        label = driver.find_element(By.XPATH, f"//label[contains(text(), '{label_text}')]")
        input_field = label.find_element(By.XPATH, "./following-sibling::input | ./following-sibling::textarea")
        input_field.clear()
        input_field.send_keys(value)
        logging.info(f"Filled {label_text} with {value}")
    except NoSuchElementException:
        logging.warning(f"Could not find input field for label: {label_text}")


def select_dropdown(driver, label_text, value):
    
    try:
        label = driver.find_element(By.XPATH, f"//label[contains(text(), '{label_text}')]")
        dropdown = label.find_element(By.XPATH, "./following-sibling::select")
        for option in dropdown.find_elements(By.TAG_NAME, "option"):
            if option.text == value:
                option.click()
                logging.info(f"Selected {value} for {label_text}")
                break
    except NoSuchElementException:
        logging.warning(f"Could not find dropdown for label: {label_text}")


def click_element(driver, xpath, description):

    try:
        element = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
        driver.execute_script("arguments[0].scrollIntoView();", element)
        element.click()
        logging.info(f"Clicked {description}")
    except (TimeoutException, ElementClickInterceptedException) as e:
        logging.error(f"Failed to click {description}: {e}")

def fill_name_fields(driver):

    input_value = {
                "first_name" : resume_data.get("first_name"),
                "last_name" : resume_data.get("last_name"),
                "pronouns" : resume_data.get("pronouns"),
                "email" : resume_data.get("email"),
                "phone" : resume_data.get("phone"),
                "address": resume_data.get("address"),
                "city" : resume_data.get("city"),
                "state" : resume_data.get("state"),
                "zip" : resume_data.get("zip"),
                "country" : resume_data.get("country"),
                "referred" : resume_data.get("referred"),
                "compensation" : resume_data.get("compensation"),
                "work_status" : resume_data.get("work_status"),
                "work_authorization" : resume_data.get("work_authorization")
    

    }

    fields = {
                "first_name" : "//label[contains(text(), 'First Name')]/following-sibling::div//input",
                "last_name" : "//label[contains(text(), 'Last Name')]/following-sibling::div//input",
                "pronouns" : "//label[contains(text(), 'Preferred Pronouns')]/following-sibling::div//select",
                "email" : "//label[contains(text(), 'Email')]/following-sibling::div//input",
                "phone" : "//label[contains(text(), 'Phone')]/following-sibling::div//input",
                "address" : "//label[contains(text(), 'Address')]/following-sibling::div//input",
                "city" : "//label[contains(text(), 'City')]/following-sibling::div//input",
                "state" : "//label[contains(text(), 'State')]/following-sibling::div//select",
                "zip" : "//label[contains(text(), 'Zip')]/following-sibling::div//input",
                "country" : "//label[contains(text(), 'Country')]/following-sibling::div//select",
                "referred" : "//label[contains(text(), 'referred by')]/following-sibling::div/input",
                "compensation" : "//label[contains(text(), 'Desired Compensation')]/following-sibling::div/input",
                "work_status" : "//label[contains(text(), 'Work Status')]/following-sibling::div//select",
                "work_authorization" : "//label[contains(text(), 'Work Authorization')]/following-sibling::div//select",



    }
   

    def fill_field(field_xpath,field_value):

        try:
            field_ip  = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, field_xpath))
        )
           
            try:
                field_ip.clear()
                field_ip.send_keys(field_value)
            except Exception as e:
                select = Select(field_ip)
                select.select_by_visible_text(field_value)
                print(f'-------------------select input selected with value {field_value}')
        except Exception as e:
            print(f"{e}{field_xpath} filed not found , can't enter the field values ----------------")
   
    for key,value in fields.items():
        fill_field(value,input_value[key])





def upload_resume(driver, resume_path):
    
    try:
        file_input = driver.find_element(By.XPATH, "//input[@type='file']")
        file_input.send_keys(resume_path)  
        logging.info(f"Uploaded resume from {resume_path}")
        
        time.sleep(1)

        pyautogui.press("esc")
        logging.info("Pressed ESC to close the file selection dialog.")

        fill_name_fields(driver)

        time.sleep(5)
    except NoSuchElementException:
        logging.error("File input element not found for resume upload")


def apply_to_job(job_link):
    
    logging.info(f"Opening job link: {job_link}")
    driver.get(job_link)

    try:
        apply_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Apply') or contains(@class, 'apply-button')]")))
        apply_button.click()
        logging.info("Clicked Apply button.")
        time.sleep(3)  

        select_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Select')]")))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", select_button)
        time.sleep(1)

        try:
            select_button.click()
            logging.info("Clicked Select button for resume upload.")
        except Exception as e:
            logging.warning(f"Click intercepted. Trying JavaScript click instead. Error: {e}")
            driver.execute_script("arguments[0].click();", select_button)

        file_option_xpath = "//*[@id='attachmentDropdown']/div[2]/label/span[contains(text(), 'File')]"
        file_option = wait.until(EC.element_to_be_clickable((By.XPATH, file_option_xpath)))

        
        driver.execute_script("arguments[0].scrollIntoView();", file_option)
        file_option.click()
        logging.info("Clicked 'File' option for resume upload.")

        upload_resume(driver, resume_path)

    
        next_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Next')]")))
        next_button.click()
        time.sleep(20)
        logging.info("Next Button Clicked  successfully!")


        with open("config.yaml", "r") as file:
            resume_data = yaml.safe_load(file) 


        gender_mapping = {
            "Male": "jv-field-gender-0",
            "Female": "jv-field-gender-1",
            "decline": "jv-field-gender-2"
        }

        
        selected_gender = resume_data.get("gender")
        print(f"------------------------------------------------selected_gender________--------------{selected_gender}")
        gender_value = gender_mapping.get(selected_gender)

        try:
        
            print("------------------strated gender selection--------------------------")
            radio_button = wait.until(EC.element_to_be_clickable((By.ID, gender_mapping[selected_gender])))
            driver.execute_script("arguments[0].scrollIntoView(true);", radio_button) 
            driver.execute_script("arguments[0].click();", radio_button) 
            print(f"Selected {selected_gender} successfully.")
        except Exception as e:
            print(f"Error selecting {selected_gender}: {e}")



    
        
        send_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'jv-button-primary') and contains(., 'Send Application')]")))
        
        driver.execute_script("arguments[0].click();", send_button)
        logging.info("Clicked 'Send Application' button.")

        confirmation_message = wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'Your application has been submitted')]")))
        logging.info("Application submitted successfully!")

    except TimeoutException:
        logging.error(f"Timeout: Could not find elements for job {job_link}")
    except NoSuchElementException as e:
        logging.error(f"Error applying for job: {e}")

    


def main():
    for job in config["jobvite"]["job_links"]:
        apply_to_job(job)
    driver.quit()


if __name__ == "__main__":
    main()
