# HOWDY! SEEK
import json
from time import sleep
import requests
import random
import traceback

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC

chrome_options = Options()
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument(r'user-data-dir=/home/michael/.config/chromium/')
chrome_options.add_argument('--profile-directory=Default')
chrome_options.add_experimental_option('detach', True)
driver = webdriver.Chrome(options=chrome_options)

with open('config.json', 'r') as file:
    data = json.load(file)


def create_tabs():
    # first let's create a list of all the classes we want
    courses = set()
    for webhook, sections in data.items():
        for section in sections:
            courses.add(section["course"])

    first = True
    for course_json in courses:
        # avoid creating a new tab for the first navigation
        if first:
            first = False
            driver.get(
                "https://tamu.collegescheduler.com/terms/Spring%202025%20-%20College%20Station/options")
            # firstly we need to choose the correct term
            WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="Spring 2025 - College Station"]'))).click()
            # then submit (part 1)
            WebDriverWait(driver, 1).until(EC.element_to_be_clickable(
                (By.XPATH, '//*[@id="scheduler-app"]/div/main/div/div/div/div[2]/div/div/button/span[2]'))).click()
        else:
            # otherwise we don't need to choose the term
            driver.switch_to.new_window('tab')
            driver.get(
                "https://tamu.collegescheduler.com/terms/Spring%202025%20-%20College%20Station/options")

        WebDriverWait(driver, 20).until(EC.presence_of_element_located(
            (By.XPATH, '//*[@id="scheduler-app"]/div/main/div/div/div[1]/div/div[4]/div[1]/div[1]/div[1]/div/div[2]')))

        WebDriverWait(driver, 20).until(EC.presence_of_element_located(
            (By.XPATH, '//*[@id="scheduler-app"]/div/main/div/div/div[2]/div[1]/div/div[2]/table')))

        # now we need to load course section information for each course
        course_elements = driver.find_elements(By.CLASS_NAME, 'css-131ktj-rowCss')
        for course_element in course_elements:
            course = course_element.find_elements(By.XPATH, './*')[1].get_attribute('innerText')
            # found a matching course with our json, let us designate this tab for that course
            if course.split("\n")[0] == course_json:
                section_button = course_element.find_element(By.XPATH, './td[3]/div/div/div[1]/a')
                section_button.click()
                break  # break or else stale element


def check_sections():
    # firstly let us extract the crns of each course and the seats open for each course
    # recall that this is only on the enabled page
    section_info = {}

    # respectfully, this mogs any other waits
    # pair this with the offscreen_compiled.js skip.
    WebDriverWait(driver, 20).until(EC.presence_of_element_located(
        (By.CLASS_NAME, 'css-1p12g40-cellCss-hideOnMobileCss')))

    labels = driver.find_elements(By.CLASS_NAME, 'css-1p12g40-cellCss-hideOnMobileCss')
    if len(labels) < 6:  # shouldn't ever happen
        source_code = driver.page_source
        with open("page_source.html", "w", encoding="utf-8") as file:
            file.write(source_code)
        print("Error: no classes found. Source saved.")
    # cool pattern: the CRN is every 6, and the seats open is every CRN index plus 3
    # :-)
    for label in range(0, len(labels), 6):
        crn = labels[label].text
        seats = labels[label + 3].text
        section_info[crn] = seats

    # loop through all courses in each webhook and find matches
    for webhook, classes in data.items():
        for section in classes:
            crn = section["crn"]
            # crn match
            # recall that only enabled sections are scraped
            # therefore the crns in section_info will all be available

            # there's probably optimization here to be done but it werks
            # maybe optimize with driver.current_url and rfind('/') + 1

            if crn in section_info:
                course = section["course"]
                prof = section["prof"]

                notify(webhook, "SEATS AVAILABLE",
                       f'{course} with {prof} is available.\nCRN: {crn}\nAggie Schedule Builder: https://tamu.collegescheduler.com/terms/Spring%202025%20-%20College%20Station/options')


def notify(webhook, title, description):
    discord_json = {
        "embeds": [{"description": description, "title": title}]
    }
    result = requests.post(webhook, json=discord_json)
    try:
        result.raise_for_status()
    except requests.exceptions.HTTPError as err:
        print(err)


if __name__ == "__main__":
    create_tabs()
    while True:
        for i in driver.window_handles:
            try:
                driver.switch_to.window(i)
                # random invalid page lol. skip cause it messes up everything
                if "offscreen_compiled.js" in driver.page_source:
                    continue

                # howdyseek is indestructible!
                invalid_string = "invalid.aspx?aspxerrorpath=/"
                if invalid_string in driver.current_url:
                    url = driver.current_url
                    url = url.replace(invalid_string, "")
                    print("Page error detected. Redirecting to " + url)
                    driver.get(url)
                else:
                    driver.refresh()

                check_sections()
            except Exception as e:
                traceback.print_exc()
                pass
        sleep(random.uniform(15, 25))  # or 30, 40
