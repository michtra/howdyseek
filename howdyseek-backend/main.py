"""
HOWDY! SEEK
"""

import random
import time
import traceback
import re

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

# Import configuration from config.py
from config import (
    USER_DATA_DIR_ARG, PROFILE_DIR_ARG, TAMU_SCHEDULER_BASE_URL, 
    FALL_2025_URL, TERM_STRING, API_BASE_URL, INVALID_PAGE_STRING, 
    DEFAULT_REFRESH_INTERVAL_RANGE
)

# Global tracking variables
FIRST_TAB_CREATED = False
KNOWN_EMPTY_SECTIONS = []  # CRNs of courses known to currently have no sections


class HowdySeek:
    def __init__(self):
        """Constructor."""
        self.data = self._load_config()
        self.course_names = {}  # Maps URL ID to course name
        self.section_states = {}  # Maps course names to {crn: seats} dictionaries
        self.tab_links = {}  # Maps window handles to URLs
        self.refresh_interval_range = self._load_refresh_settings()
        self.monitored_courses = set()  # Track which courses are currently being monitored

        # Initialize WebDriver
        self.driver = self._setup_webdriver()

    @staticmethod
    def _setup_webdriver() -> webdriver.Chrome:
        """Configure and return a webdriver."""
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        # bug fix
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument(USER_DATA_DIR_ARG)
        chrome_options.add_argument(PROFILE_DIR_ARG)
        chrome_options.add_experimental_option('detach', True)
        return webdriver.Chrome(options=chrome_options)

    def _load_refresh_settings(self) -> tuple:
        """Load refresh interval settings from the API."""
        try:
            response = requests.get(f"{API_BASE_URL}/settings/")
            if response.status_code != 200:
                print(f"Failed to fetch settings: {response.text}")
                return DEFAULT_REFRESH_INTERVAL_RANGE

            settings = response.json()
            return (settings['min_refresh_interval'], settings['max_refresh_interval'])
        except Exception as e:
            print(f"Error loading refresh settings from API: {e}")
            traceback.print_exc()
            return DEFAULT_REFRESH_INTERVAL_RANGE

    def _load_config(self) -> dict:
        """Load configuration from the API. 
        Format the data to match the original JSON structure for compatibility."""
        try:
            # Get all users from the API
            response = requests.get(f"{API_BASE_URL}/users/")
            if response.status_code != 200:
                print(f"Failed to fetch users: {response.text}")
                return {}

            users = response.json()

            # Format data to match the original structure
            config = {}
            for user in users:
                # Use webhook_url as the key
                webhook = user['webhook_url']
                courses = []

                for course in user['courses']:
                    courses.append({
                        "prof": course['professor'],
                        "course": course['course_name'],
                        "crn": course['crn']
                    })

                if courses:  # Only add to config if there are courses
                    config[webhook] = courses

            # Also refresh the interval settings
            self.refresh_interval_range = self._load_refresh_settings()

            return config
        except Exception as e:
            print(f"Error loading config from API: {e}")
            traceback.print_exc()
            return {}

    def _get_all_courses(self) -> set:
        """Extract all unique courses from the current configuration."""
        courses = set()
        for webhook, sections in self.data.items():
            for section in sections:
                courses.add(section["course"])
        return courses

    def initialize_first_tab(self):
        """Initialize the first tab with correct term selection.
        This is called only when the first tab is created."""
        global FIRST_TAB_CREATED
        
        # If first tab already initialized, do nothing
        if FIRST_TAB_CREATED:
            return
        
        # Navigate to the term selection page
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
        
        # Mark first tab as created
        FIRST_TAB_CREATED = True
        
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

    def create_tab_for_course(self, course_name: str) -> bool:
        """Create a browser tab for a specific course.
        
        Args:
            course_name: The name of the course to create a tab for
            
        Returns:
            bool: True if tab was created successfully, False otherwise
        """
        global FIRST_TAB_CREATED
        
        # Skip if already monitoring this course
        if course_name in self.monitored_courses:
            return True
            
        try:
            # Always check if first tab needs to be initialized
            if not FIRST_TAB_CREATED:
                self.initialize_first_tab()
                
                # Look for the course in the list
                course_elements = self.driver.find_elements(By.CLASS_NAME, 'css-131ktj-rowCss')

                for course_element in course_elements:
                    # Extract the course name from the element
                    course = course_element.find_elements(By.XPATH, './*')[1].get_attribute('innerText')
                    # Bug fix: use regex grab the correct course name. new format as of Fall 2025 registration
                    match = re.match(r"(\w+ \d+)", course)
                    course = match.group(1)

                    # Found a matching course with our json, let us designate this tab for that course
                    if course == course_name:
                        # Click on the section button
                        section_button = course_element.find_element(By.XPATH, './td[3]/div/div/div[1]/a')
                        section_button.click()

                        # Wait for the page to change from options
                        while "options" in self.driver.current_url:
                            time.sleep(0.01)

                        # Extract the URL ID and map it to the course name
                        url_id = self.driver.current_url.split('/')[-1]
                        self.course_names[url_id] = course_name
                        
                        # Store current URL in tab_links
                        self.tab_links[self.driver.current_window_handle] = self.driver.current_url
                        
                        # Mark course as monitored
                        self.monitored_courses.add(course_name)
                        return True
                
                # If we get here and it's the first tab, but course wasn't found,
                # still mark the first tab as created, since we'll need to create a new tab anyway
                return False
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

                # Look for the course in the list
                course_elements = self.driver.find_elements(By.CLASS_NAME, 'css-131ktj-rowCss')

            for course_element in course_elements:
                # Extract the course name from the element
                course = course_element.find_elements(By.XPATH, './*')[1].get_attribute('innerText')
                # Bug fix: use regex grab the correct course name. new format as of Fall 2025 registration
                match = re.match(r"(\w+ \d+)", course)
                course = match.group(1)

                # Found a matching course with our json, let us designate this tab for that course
                if course == course_name:
                    # Click on the section button
                    section_button = course_element.find_element(By.XPATH, './td[3]/div/div/div[1]/a')
                    section_button.click()

                    # Wait for the page to change from options
                    while "options" in self.driver.current_url:
                        time.sleep(0.01)

                    # Extract the URL ID and map it to the course name
                    url_id = self.driver.current_url.split('/')[-1]
                    self.course_names[url_id] = course_name
                    
                    # Store current URL in tab_links
                    self.tab_links[self.driver.current_window_handle] = self.driver.current_url
                    
                    # Mark course as monitored
                    self.monitored_courses.add(course_name)
                    
                    return True
            
            # If we get here, course wasn't found
            print(f"Course {course_name} not found in scheduler")
            return False
            
        except Exception as e:
            print(f"Error creating tab for course {course_name}: {e}")
            traceback.print_exc()
            return False

    def create_tabs(self):
        """Create browser tabs for each unique course in the configuration."""
        global FIRST_TAB_CREATED
        
        # Get all unique courses from config
        courses = self._get_all_courses()
        
        # If no courses, nothing to do
        if not courses:
            return
            
        # Create first tab if not already created
        if not FIRST_TAB_CREATED:
            # Initialize first tab, regardless of whether we'll use it for a course
            self.initialize_first_tab()
            
            # If we have courses, assign the first one to this tab
            if courses:
                first_course = next(iter(courses))
                
                # Look for the course in the list
                course_elements = self.driver.find_elements(By.CLASS_NAME, 'css-131ktj-rowCss')

                for course_element in course_elements:
                    # Extract the course name from the element
                    course = course_element.find_elements(By.XPATH, './*')[1].get_attribute('innerText')
                    # Bug fix: use regex grab the correct course name. new format as of Fall 2025 registration
                    match = re.match(r"(\w+ \d+)", course)
                    course = match.group(1)

                    # Found a matching course with our json, let us designate this tab for that course
                    if course == first_course:
                        # Click on the section button
                        section_button = course_element.find_element(By.XPATH, './td[3]/div/div/div[1]/a')
                        section_button.click()

                        # Wait for the page to change from options
                        while "options" in self.driver.current_url:
                            time.sleep(0.01)

                        # Extract the URL ID and map it to the course name
                        url_id = self.driver.current_url.split('/')[-1]
                        self.course_names[url_id] = first_course
                        
                        # Store current URL in tab_links
                        self.tab_links[self.driver.current_window_handle] = self.driver.current_url
                        
                        # Mark course as monitored
                        self.monitored_courses.add(first_course)
                        
                        # Remove first course so we don't create a new tab for it
                        courses.remove(first_course)
                        break
        
        # Create tabs for remaining courses using create_tab_for_course
        # This ensures we handle the first tab initialization if needed
        for course_name in courses:
            if course_name not in self.monitored_courses:
                self.create_tab_for_course(course_name)

    def check_for_new_courses(self):
        """Check for new courses added to the configuration and create tabs for them."""
        global FIRST_TAB_CREATED
        
        # Reload config to get the latest courses
        new_data = self._load_config()
        
        # Extract all courses from the updated config
        new_courses = set()
        for webhook, sections in new_data.items():
            for section in sections:
                new_courses.add(section["course"])
        
        # Find courses that aren't being monitored yet
        courses_to_add = new_courses - self.monitored_courses
        
        # Update the stored data
        self.data = new_data
        
        # If we have courses to add but first tab isn't created yet, use create_tabs()
        if courses_to_add and not FIRST_TAB_CREATED:
            self.create_tabs()
            return len(courses_to_add) > 0
            
        # If first tab already exists, create tabs for new courses
        for course_name in courses_to_add:
            self.create_tab_for_course(course_name)
            
        return len(courses_to_add) > 0

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

        # Process all sections and send notifications for changes
        for webhook, classes in self.data.items():
            for section in classes:
                crn = section["crn"]

                # Skip if the course doesn't match the current one
                if section["course"] != current_course:
                    continue

                # Handle sections that are currently visible
                if crn in visible_sections:
                    prev_seats = self.section_states[current_course].get(crn, None)
                    current_seats = visible_sections[crn]

                    # New section or seat change detected
                    if prev_seats is None or prev_seats != current_seats:
                        course = section["course"]
                        prof = section["prof"]

                        status = f'Seats Available ({current_seats})' if prev_seats is None else f'Seat Change: {prev_seats} → {current_seats}'
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
        # Initial tab creation
        self.create_tabs()
        
        while True:
            # Check for new courses every cycle
            self.check_for_new_courses()

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
                    # Remove this handle from our tracking
                    if window_handle in self.tab_links:
                        del self.tab_links[window_handle]
                except WebDriverException:
                    pass
                except Exception:
                    traceback.print_exc()
                    pass

            # Sleep for a random interval using current settings
            time.sleep(random.uniform(*self.refresh_interval_range))


if __name__ == "__main__":
    try:
        monitor = HowdySeek()
        monitor.run()
    except Exception as e:
        traceback.print_exc()