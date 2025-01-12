# HOWDY! SEEK
import json
from time import sleep
import requests
import random
import traceback

import selenium.common.exceptions
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


# loads configuration from the JSON file. allows for config changes on the go;
# particularly, removing webhooks or adding notifications to preexisting courses on the schedule builder
def load_config():
    global data
    with open('config.json', 'r') as file:
        data = json.load(file)
    return data


# initial config load
data = load_config()
course_names = {}  # Format: {url id: course name}


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
                # now let us map this url number to the course name
                # this will allow us to not repeatedly notify
                while "options" in driver.current_url:
                    sleep(0.01)
                # page url id is the number at the end of the url
                url_id = driver.current_url.split('/')[-1]
                course_names[url_id] = course_json
                break  # break here or else stale element in the for loop


# howdyseek is literally indestructible
def redirect_if_invalid():
    invalid_string = "invalid.aspx?aspxerrorpath=/"
    if invalid_string in driver.current_url:
        url = driver.current_url
        url = url.replace(invalid_string, "")
        print("Page error detected. Redirecting to " + url)
        driver.get(url)
        return True
    return False


def has_no_sections():
    if driver.find_elements(By.XPATH, '//*[@id="scheduler-app"]/div/main/div/div/div[2]/ul/li[1]/a/span'):
        text = driver.find_element(By.XPATH, '//*[@id="scheduler-app"]/div/main/div/div/div[2]/ul/li[1]/a/span').text
        return text == "Enabled (0 of 0)"
    return False


section_states = {}


def check_sections(current_link):
    current_course = None
    current_url_id = current_link.split('/')[-1]
    for url_id, course in course_names.items():
        if url_id == current_url_id:
            current_course = course
            break

    # shouldn't ever happen but just in case
    if not current_course:
        return

    # Initialize section state for this source if it doesn't exist
    # maps crns to current seats available
    if current_course not in section_states:
        section_states[current_course] = {}

    # firstly let us extract the crns of each course and the seats open for each course
    # recall that this is only on the enabled page
    # we can extract section information only if there are sections available to extract
    # thus we first must wait an adequate amount of time for section information to appear
    visible_sections = {}

    no_sections = [
        "6020115" # PERF 301
    ]

    success = False
    # two different waits
    # wait #1 is for classes that currently have no sections available in the "Enabled" tab
    # we can assume that they probably still don't have sections so we wait a shorter amount of time for them
    if current_link.split('/')[-1] in no_sections:
        while not success:
            try:
                # wait only 3 seconds to see if section information appears
                WebDriverWait(driver, 2).until(EC.presence_of_element_located(
                    (By.CLASS_NAME, 'css-1p12g40-cellCss-hideOnMobileCss')))
                success = True
            except:
                # at this point, there is no section information.
                # the page may be errored out or there are simply no sections

                # do error handling before checking if sections are available
                if "invalid request" in driver.page_source:
                    # refresh if invalid request
                    driver.get(current_link)
                elif driver.find_element(By.CLASS_NAME, 'spinner'):
                    # or refresh if still loading / erroring out
                    driver.get(current_link)

                # check if there are no sections available
                if has_no_sections():
                    # break and don't toggle success to True
                    break
    # wait #2 is for normal classes with at least one section available
    else:
        # unlike the previous one, we should wait longer for a section element to show up
        # if a section element doesn't show up, it's an errored page, just refresh
        while not success:
            try:
                # wait for the first section to show up on screen
                # we can assume all the other sections show up as well at the same time
                WebDriverWait(driver, 5).until(EC.presence_of_element_located(
                    (By.CLASS_NAME, 'css-1p12g40-cellCss-hideOnMobileCss')))
                success = True
            except:
                # in the case that there are no sections
                if has_no_sections():
                    # break and don't toggle success to True
                    break

                # otherwise refresh and retry. could be a page error or just a timeout
                driver.get(current_link)

    # at this point, success is True. there are sections to check.
    # but if it's False, it's because there are no sections available from wait #1. Skip this class.
    if not success:
        return

    labels = driver.find_elements(By.CLASS_NAME, 'css-1p12g40-cellCss-hideOnMobileCss')
    # cool pattern: the CRN is every 6, and the seats open is every CRN index plus 3
    # :-)
    for label in range(0, len(labels), 6):
        crn = labels[label].text
        seats = int(labels[label + 3].text)
        visible_sections[crn] = seats

    global data
    data = load_config()
    # loop through all courses in each webhook and find matches
    for webhook, classes in data.items():
        for section in classes:
            crn = section["crn"]
            # crn match
            if crn in visible_sections:
                # check if this is a new section or if seats have changed
                prev_seats = section_states[current_course].get(crn, None)
                current_seats = visible_sections[crn]

                # new section or seat change detected
                if prev_seats is None or prev_seats != current_seats:
                    course = section["course"]
                    prof = section["prof"]

                    status = "SEATS AVAILABLE" if prev_seats is None else f'SEAT CHANGE: {prev_seats} → {current_seats}'
                    notify(webhook, status,
                           f'{course} with {prof} is available.\nCRN: {crn}\nAggie Schedule Builder: https://tamu.collegescheduler.com/terms/Spring%202025%20-%20College%20Station/options')

                    # Update state
                    section_states[current_course][crn] = current_seats
            # if a section was previously visible but now isn't, it means it now has 0 seats
            elif crn in section_states[current_course]:
                prev_seats = section_states[current_course][crn]
                if prev_seats > 0:  # only notify if previously seats available
                    course = section["course"]
                    prof = section["prof"]
                    notify(webhook, "Section Full",
                           f'{course} with {prof} is now full.\nCRN: {crn}')
                # Update state
                section_states[current_course][crn] = 0


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
    # links dictionary for each tab.
    # created because a page may error and the corresponding course url to the page may be lost
    links = {}
    while True:
        for i in driver.window_handles:
            try:
                driver.switch_to.window(i)
                # random invalid page lol. skip cause it messes up everything
                if "offscreen_compiled.js" in driver.page_source:
                    continue

                # dictionary should be created successfully on the first iteration
                if i not in links:
                    links[i] = driver.current_url
                current_link = links[i]

                # if not refreshed from an invalid page then refresh
                if not redirect_if_invalid():
                    driver.refresh()

                check_sections(current_link)
            except selenium.common.exceptions.NoSuchWindowException:
                pass
            except selenium.common.exceptions.WebDriverException:
                pass
            except Exception as e:
                traceback.print_exc()
                pass
        sleep(random.uniform(30, 40))  # or 30, 40
