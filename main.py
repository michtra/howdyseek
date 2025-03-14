"""
HOWDY! SEEK
"""

import json
import random
import time
import traceback

import requests
from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchWindowException,
    WebDriverException,
    TimeoutException
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
# noinspection PyPep8Naming
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# Constants
TAMU_SCHEDULER_BASE_URL = "https://tamu.collegescheduler.com"
FALL_2025_URL = f"{TAMU_SCHEDULER_BASE_URL}/terms/Fall%202025%20-%20College%20Station/options"
TERM_STRING = '//*[@id="Fall 2025 - College Station"]'
INVALID_PAGE_STRING = "invalid.aspx?aspxerrorpath=/"
REFRESH_INTERVAL_RANGE = (30, 40)  # Seconds
KNOWN_EMPTY_SECTIONS = []  # CRNs of courses known to currently have no sections
# this is to deploy an optimal waiting strategy

class HowdySeek:
    def __init__(self, config_file: str = 'config.json'):
        """Constructor.

        Args:
            config_file: Path to the configuration JSON file
        """
        self.config_file = config_file
        self.data = self._load_config()
        self.course_names = {}  # Maps URL ID to course name
        self.section_states = {}  # Maps course names to {crn: seats} dictionaries
        self.tab_links = {}  # Maps window handles to URLs
        
        # Initialize WebDriver
        self.driver = self._setup_webdriver()
    
    @staticmethod
    def _setup_webdriver() -> webdriver.Chrome:
        """Configure and return a webdriver."""
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument(r'user-data-dir=/home/michael/.config/chromium/')
        chrome_options.add_argument('--profile-directory=Profile 7') # or Profile 7 (those who know)
        chrome_options.add_experimental_option('detach', True)
        return webdriver.Chrome(options=chrome_options)
    
    def _load_config(self) -> dict:
        """Load configuration from the JSON file. 
        Allows for config changes on the go; particularly, removing webhooks
        or adding notifications to preexisting courses on the schedule builder."""
        try:
            with open(self.config_file, 'r') as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            raise
    
    def create_tabs(self):
        """Create browser tabs for each unique course in the configuration."""
        # Collect all unique courses from config
        courses = set()
        for webhook, sections in self.data.items():
            for section in sections:
                courses.add(section["course"])

        first_tab = True
        for course_name in courses:
            if first_tab:
                # For the first tab, navigate and select the term
                self.driver.get(FALL_2025_URL)

                # Select the correct term
                WebDriverWait(self.driver, 20).until(
                    EC.element_to_be_clickable((By.XPATH, TERM_STRING))
                ).click()

                # Submit selection
                WebDriverWait(self.driver, 1).until(
                    EC.element_to_be_clickable((
                        By.XPATH, 
                        '//*[@id="scheduler-app"]/div/main/div/div/div/div[2]/div/div/button/span[2]'
                    ))
                ).click()
                
                first_tab = False
            else:
                # For subsequent tabs, open a new tab
                self.driver.switch_to.new_window('tab')
                self.driver.get(FALL_2025_URL)
            
            # Wait for course list to load
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((
                    By.XPATH, 
                    '//*[@id="scheduler-app"]/div/main/div/div/div[1]/div/div[4]/div[1]/div[1]/div[1]/div/div[2]'
                ))
            )
            
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((
                    By.XPATH, 
                    '//*[@id="scheduler-app"]/div/main/div/div/div[2]/div[1]/div/div[2]/table'
                ))
            )
            
            course_elements = self.driver.find_elements(By.CLASS_NAME, 'css-131ktj-rowCss')
            
            for course_element in course_elements:
                # Extract the course name from the element
                course = course_element.find_elements(By.XPATH, './*')[1].get_attribute('innerText')
                
                # Found a matching course with our json, let us designate this tab for that course
                if course.split("\n")[0] == course_name:
                    # Click on the section button
                    section_button = course_element.find_element(By.XPATH, './td[3]/div/div/div[1]/a')
                    section_button.click()
                    
                    # Wait for the page to change from options
                    while "options" in self.driver.current_url:
                        time.sleep(0.01)
                    
                    # Extract the URL ID and map it to the course name
                    # This will allow us to not repeatedly notify
                    url_id = self.driver.current_url.split('/')[-1]
                    self.course_names[url_id] = course_name
                    break  # Break after finding the course to avoid stale elements
    
    def redirect_if_invalid(self) -> bool:
        """Check if the current page has an error and redirect if needed.
        
        Returns:
            True if a redirect was performed, False otherwise
        """
        if INVALID_PAGE_STRING in self.driver.current_url:
            url = self.driver.current_url.replace(INVALID_PAGE_STRING, "")
            self.driver.get(url)
            return True
        return False
    
    def has_no_sections(self) -> bool:
        """Check if the current course has no sections available.
        
        Returns:
            True if there are no sections, False otherwise
        """
        if self.driver.find_elements(By.XPATH, '//*[@id="scheduler-app"]/div/main/div/div/div[2]/ul/li[1]/a/span'):
            text = self.driver.find_element(
                By.XPATH, '//*[@id="scheduler-app"]/div/main/div/div/div[2]/ul/li[1]/a/span'
            ).text
            return text == "Enabled (0 of 0)"
        return False
    
    def check_sections(self, current_link: str):
        """Check for section availability changes and send notifications.
        
        Args:
            current_link: The URL of the current tab
        """
        # Get the course name corresponding to this URL ID
        current_url_id = current_link.split('/')[-1]
        current_course = None
        
        for url_id, course in self.course_names.items():
            if url_id == current_url_id:
                current_course = course
                break
        
        # Skip if we can't identify the course (shouldn't ever happen)
        if not current_course:
            return
        
        # Initialize section state for this course if it doesn't exist
        if current_course not in self.section_states:
            self.section_states[current_course] = {}
        
        # Extract visible sections and their availability
        visible_sections = {}
        
        success = False
        
        # Different wait strategy based on whether we expect this course to have sections
        if current_link.split('/')[-1] in KNOWN_EMPTY_SECTIONS:
            # Wait #1 is for classes that currently have no sections available in the "Enabled" tab
            # We can assume that they probably still don't have sections so we wait a shorter amount of time for them
            while not success:
                try:
                    # Wait only 2 seconds to see if section information appears
                    WebDriverWait(self.driver, 2).until(
                        EC.presence_of_element_located((By.CLASS_NAME, 'css-1p12g40-cellCss-hideOnMobileCss'))
                    )
                    success = True
                except TimeoutException:
                    # At this point, there is no section information.
                    # The page may be errored out or there are simply no sections

                    # Do error handling before checking if sections are available
                    if "invalid request" in self.driver.page_source:
                        # Refresh if invalid request
                        self.driver.get(current_link)
                    elif self.driver.find_elements(By.CLASS_NAME, 'spinner'):
                        # Or refresh if still loading / erroring out
                        self.driver.get(current_link)
                    
                    # Check if there are no sections available
                    if self.has_no_sections():
                        # Break and don't toggle success to True
                        break
        else:
            # Wait #2 is for normal classes with at least one section available
            # Unlike the previous one, we should wait longer for a section element to show up
            # If a section element doesn't show up, it's an errored page, just refresh
            while not success:
                try:
                    # Wait for the first section to show up on screen
                    # We can assume all the other sections show up as well at the same time
                    WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CLASS_NAME, 'css-1p12g40-cellCss-hideOnMobileCss'))
                    )
                    success = True
                except TimeoutException:
                    # In the case that there are no sections
                    if self.has_no_sections():
                        # Break and don't toggle success to True
                        break
                    
                    # Otherwise refresh and retry. Could be a page error or just a timeout
                    self.driver.get(current_link)
        
        # At this point, success is True. There are sections to check.
        # But if it's False, it's because there are no sections available from wait #1. Skip this class.
        if not success:
            return
        
        # Extract section information
        try:
            labels = self.driver.find_elements(By.CLASS_NAME, 'css-1p12g40-cellCss-hideOnMobileCss')
            
            # Cool pattern: the CRN is every 6, and the seats open is every CRN index plus 3
            # :-)
            for label in range(0, len(labels), 6):
                crn = labels[label].text
                seats = int(labels[label + 3].text)
                visible_sections[crn] = seats
                
        except Exception:
            return
        
        # Reload config to check for any updates
        self.data = self._load_config()
        
        # Process all sections and send notifications for changes
        for webhook, classes in self.data.items():
            for section in classes:
                crn = section["crn"]
                
                # Handle sections that are currently visible
                if crn in visible_sections:
                    prev_seats = self.section_states[current_course].get(crn, None)
                    current_seats = visible_sections[crn]
                    
                    # New section or seat change detected
                    if prev_seats is None or prev_seats != current_seats:
                        course = section["course"]
                        prof = section["prof"]
                        
                        status = "SEATS AVAILABLE" if prev_seats is None else f'SEAT CHANGE: {prev_seats} → {current_seats}'
                        message = (
                            f'{course} with {prof} is available.\n'
                            f'CRN: {crn}\n'
                            f'Aggie Schedule Builder: {FALL_2025_URL}'
                        )
                        
                        self._send_notification(webhook, status, message)
                        
                        # Update state
                        self.section_states[current_course][crn] = current_seats
                
                # Handle sections that were previously visible but now aren't
                elif crn in self.section_states[current_course]:
                    prev_seats = self.section_states[current_course][crn]
                    
                    # Only notify if previously seats were available
                    if prev_seats > 0:
                        course = section["course"]
                        prof = section["prof"]
                        
                        message = f'{course} with {prof} is now full.\nCRN: {crn}'
                        self._send_notification(webhook, "Section Full", message)
                    
                    # Update state
                    self.section_states[current_course][crn] = 0
    
    @staticmethod
    def _send_notification(webhook: str, title: str, description: str):
        """Send a Discord notification.
        
        Args:
            webhook: The Discord webhook URL
            title: The notification title
            description: The notification description
        """
        discord_json = {
            "embeds": [{"description": description, "title": title}]
        }
        
        result = requests.post(webhook, json=discord_json)
        try:
            result.raise_for_status()
        except requests.exceptions.HTTPError as err:
            print(err)
    
    def run(self):
        """Run the course monitoring loop"""
        self.create_tabs()
        
        while True:
            for window_handle in self.driver.window_handles:
                try:
                    self.driver.switch_to.window(window_handle)
                    
                    # Skip invalid pages
                    if "offscreen_compiled.js" in self.driver.page_source:
                        continue
                    
                    # Store the URL if not already stored
                    if window_handle not in self.tab_links:
                        self.tab_links[window_handle] = self.driver.current_url
                    
                    current_link = self.tab_links[window_handle]
                    
                    # Check for invalid page and redirect if needed
                    if not self.redirect_if_invalid():
                        self.driver.refresh()
                    
                    # Check for section changes
                    self.check_sections(current_link)
                    
                except NoSuchWindowException:
                    pass
                except WebDriverException:
                    pass
                except Exception:
                    traceback.print_exc()
                    pass
            
            # Sleep for a random interval
            time.sleep(random.uniform(*REFRESH_INTERVAL_RANGE))


if __name__ == "__main__":
    try:
        monitor = HowdySeek()
        monitor.run()
    except Exception as e:
        traceback.print_exc()
