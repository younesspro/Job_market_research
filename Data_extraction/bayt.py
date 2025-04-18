from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException,ElementClickInterceptedException,ElementNotInteractableException
from selenium_init import *
import time
import re

def normalize_header(header,header_keywords):
    header = header.lower().strip()
    for norm, variations in header_keywords.items():
        if any(header.startswith(v) for v in variations):
            return norm
    return header  # fallback to raw if unmatched
def text_segmentation(job_offer_details):
    #headers
    header_keywords = {
        'job_description': ['job description', 'description'],
        'skills': ['skills', 'required skills'],
        'preferred_candidate': ['preferred candidate', 'candidate profile'],
        'company': ['company', 'about the company']
    }

    # Flatten all possible headers
    all_keywords = [kw for group in header_keywords.values() for kw in group]
    regex_pattern = r'\n(?=({}))'.format('|'.join(map(re.escape, all_keywords)))

    # Split using regex
    sections = re.split(regex_pattern, job_offer_details, flags=re.IGNORECASE)
    
    parsed_sections = {}
    parsed_sections['intro'] = sections[0].strip()

    # Parse remaining sections into normalized keys
    for i in range(1, len(sections), 2):
        header = sections[i]
        content = sections[i+1] if i+1 < len(sections) else ''
        key = normalize_header(header, header_keywords)
        parsed_sections[key] = content.strip()
    return parsed_sections


def access_bayt(driver):
    
    # Accéder à la page de base
    base_url = "https://www.bayt.com/en/morocco/"
    driver.get(base_url)
    
    # Attendre que la barre de recherche soit disponible, puis saisir "DATA"
    search_input = WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input#text_search"))
    )
    search_input.clear()
    search_input.send_keys("DATA" + Keys.RETURN)
def extract_job_details(driver:webdriver,offers=[]):
    try:
        job_title = driver.find_element(By.CSS_SELECTOR, "h2#jobViewJobTitle").text.strip()
        #print("The Job title found is: ", job_title)
    except NoSuchElementException:
        job_title = ""

    try:
        company_name = driver.find_element(By.CSS_SELECTOR, "#view_inner > div > div.toggle-head.z-hi.u-sticky-m.bg-inverse.bb-m > div.row.is-m.no-wrap.v-align-center.p10t > div > b > a").text.strip()
        #print("The company name found is: ", company_name)
    except NoSuchElementException:
        company_name = ""

    try:
        job_details=driver.find_element(By.CSS_SELECTOR, "div.u-scrolly.t-small").text.strip()
        job_details=text_segmentation(job_details)
        #print("Job details are:" ,job_details)
    except NoSuchElementException:
        job_details = ""
    offer={
        "job_title": job_title,
        "company_name": company_name,
        }
    offer|=job_details
    offers.append(offer)
    return offers

def find_number_of_pages(driver:webdriver.Chrome):
    try:
        num_of_pages = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "ul.pagination li.pagination-last-d a"))
        )
        num_of_pages = num_of_pages.get_attribute("href").split("page=")[1]
        print("Number of pages found : ", num_of_pages)
        return int(num_of_pages)
    except TimeoutException:
        print("Couldnt find number of pages.")
        
def change_page(driver:webdriver.Chrome,num_pages:int):
    try:
        next_page = int(driver.current_url.split("?page=")[1]) + 1
    except (IndexError, ValueError):
        next_page = 1
    if next_page <= num_pages:
        try:
            url=driver.current_url.split("?page=")[0] + "?page=" + str(next_page)
            driver.get(url)
            WebDriverWait(driver,10).until(EC.url_to_be(url))
            return True
        except TimeoutException:
            print("No more pages to load.")
            return False
    else:
        print("No more pages to load.")
        return False


def access_job_offer(driver : webdriver.Chrome):
    job_offers= WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "ul.media-list.in-card > li.has-pointer-d"))
            )
    offers = []
    current_url= driver.current_url
    print("Found {} job offers.".format(len(job_offers)))
    for i in range(len(job_offers)):
        try:
            job_offers= WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "ul.media-list.in-card > li.has-pointer-d"))
            )
            job_offer=job_offers[i]
            highlight(job_offer)
            driver.execute_script("arguments[0].scrollIntoView();", job_offer)
            time.sleep(0.5)
            job_offer.click()
            offers=extract_job_details(driver,offers)
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "span.icon.is-times.has-pointer.t-mute.m0"))).click()
        except (ElementClickInterceptedException, ElementNotInteractableException, NoSuchElementException) as e:
            print("An error occurred while clicking on the job offer")
            if driver.current_url != current_url:
                print("Url changed, going back.")
                driver.get(current_url)
                WebDriverWait(driver, 5).until(EC.url_to_be(current_url))
            continue
    return offers
        
def extract_job_offers(driver:webdriver.Chrome):
    try:
        data=[]
        # Accéder à la page de base
        access_bayt(driver)
        
        # Accéder aux offres d'emploi
        num_pages = find_number_of_pages(driver)
        current_page= 1
        # Changer de page si nécessaire
        while change_page(driver,num_pages):
            print("Going to page with url: ", driver.current_url)
            data.extend(access_job_offer(driver)) 
            print(f"Page number {current_page} done, cumulated offers: ", len(data))
            current_page += 1
        print("All pages done.")
    
    except Exception as e:
        print("An error occurred:", e)
    finally:
        save_json(data, filename="offres_emploi_bayt.json")
        print("Extraction terminée!")
        
driver=init_driver()
extract_job_offers(driver)
driver.quit()
