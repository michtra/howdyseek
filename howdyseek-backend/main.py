"""
HOWDY! SEEK
"""

import random
import re
import time
import traceback
from datetime import datetime, timezone, timedelta
import threading
import asyncio
import signal
import sys

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
    USER_DATA_DIR_ARG, PROFILE_DIR_ARG, FALL_2025_URL, TERM_STRING, API_BASE_URL, INVALID_PAGE_STRING,
    DEFAULT_REFRESH_INTERVAL_RANGE
)

import discord
import os
from dotenv import load_dotenv

load_dotenv()

# Create a shared termination event
termination_event = threading.Event()

force_exit = False


# Signal handler for clean shutdown
def signal_handler(sig, frame):
    print("Shutting down gracefully...")
    termination_event.set()
    global force_exit
    if force_exit:
        print("Forcing exit")
        sys.exit(1)
    force_exit = True


# Global tracking variables
FIRST_TAB_CREATED = False
COURSE_NAME_PATTERN = re.compile(r"(\w+ \d+)")


class HowdySeek:
    def __init__(self):
        """Constructor."""
        self.course_names = {}  # Maps URL ID to course name
        self.section_states = {}  # Maps course names to {crn: seats} dictionaries
        self.tab_links = {}  # Maps window handles to URLs
        self.refresh_interval_range = self._load_refresh_settings()
        self.monitored_courses = set()  # Track which courses are currently being monitored
        self.user_stop_times = {}  # Maps webhook URLs to stop times

        # Load config After initializing user_stop_times
        self.data = self._load_config()

        # Initialize WebDriver
        self.driver = self._setup_webdriver()

    @staticmethod
    def _setup_webdriver() -> webdriver.Chrome:
        """Configure and return a webdriver."""
        chrome_options = Options()
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")  # bug fix
        chrome_options.add_argument("--disable-extensions")  # bug fix
        chrome_options.add_argument(USER_DATA_DIR_ARG)
        chrome_options.add_argument(PROFILE_DIR_ARG)
        return webdriver.Chrome(options=chrome_options)

    @staticmethod
    def _load_refresh_settings() -> tuple:
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
                # Store stop time for each user keyed by webhook
                webhook = user['webhook_url']
                if user['stop_time']:
                    # Parse ISO time
                    stop_time = datetime.fromisoformat(user['stop_time'])
                    # Ensure it has timezone info
                    if stop_time.tzinfo is None:
                        # Mark as CDT
                        cdt_offset = timezone(timedelta(hours=-5))
                        stop_time = stop_time.replace(tzinfo=cdt_offset)
                        # But use UTC internally
                        stop_time = stop_time.astimezone(timezone.utc)
                    self.user_stop_times[webhook] = stop_time
                elif webhook in self.user_stop_times:
                    # Remove any previously set stop time if it's now null
                    del self.user_stop_times[webhook]

                courses = []
                for course in user['courses']:
                    courses.append({
                        "prof": course['professor'],
                        "course": course['course_name'],
                        "crn": course['crn'],
                        "last_seat_count": course.get('last_seat_count')
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
            # Skip users who have reached their stop time
            if self._user_past_stop_time(webhook):
                continue

            for section in sections:
                courses.add(section["course"])
        return courses

    def _user_past_stop_time(self, webhook: str) -> bool:
        """Check if a user has reached their stop time."""
        if webhook in self.user_stop_times:
            stop_time = self.user_stop_times[webhook]
            current_time = datetime.now(timezone.utc)

            # Make sure both datetimes are timezone-aware for comparison
            if stop_time.tzinfo is None:
                # If stop_time is naive, assume it's in UTC
                stop_time = stop_time.replace(tzinfo=timezone.utc)

            return current_time > stop_time
        return False

    def _update_course_seat_count(self, webhook: str, crn: str, seats: int):
        """Update the last known seat count for a course in the database."""
        try:
            # First, find the user by webhook URL
            response = requests.get(f"{API_BASE_URL}/users/")
            if response.status_code != 200:
                print(f"Failed to fetch users: {response.text}")
                return

            users = response.json()
            user_id = None
            course_id = None

            # Find the user and course IDs
            course_data = None
            for user in users:
                if user['webhook_url'] == webhook:
                    user_id = user['id']
                    for course in user['courses']:
                        if course['crn'] == crn:
                            course_id = course['id']
                            course_data = course  # Store the entire course data object
                            break
                    break

            if user_id is not None and course_id is not None and course_data is not None:
                # Update the course's last_seat_count
                response = requests.put(
                    f"{API_BASE_URL}/courses/{course_id}",
                    json={
                        "course_name": course_data['course_name'],
                        "professor": course_data['professor'],
                        "crn": crn,
                        "last_seat_count": seats
                    }
                )

                if response.status_code != 200:
                    print(f"Failed to update course seat count: {response.text}")
        except Exception as e:
            print(f"Error updating course seat count: {e}")
            traceback.print_exc()

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
                    match = COURSE_NAME_PATTERN.match(course)
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

                # If we get here, and it's the first tab, but course wasn't found,
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
                match = COURSE_NAME_PATTERN.match(course)
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
                    match = COURSE_NAME_PATTERN.match(course)
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

        # Extract all courses from the updated config, respecting stop times
        new_courses = set()
        for webhook, sections in new_data.items():
            # Skip users who have reached their stop time
            if self._user_past_stop_time(webhook):
                continue

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

    def _extract_sections(self, sections_dict):
        """Extract section information from the current view.

        Args:
            sections_dict: Dictionary to store the extracted sections
        """
        labels = self.driver.find_elements(By.CLASS_NAME, 'css-1p12g40-cellCss-hideOnMobileCss')

        # Cool pattern: the CRN is every 6, and the seats open is every CRN index plus 3
        # :-)
        for label in range(0, len(labels), 6):
            crn = labels[label].text
            # Sometimes seat count may not fully render, just use 0
            try:
                seats = int(labels[label + 3].text)
            except ValueError:
                seats = 0
            sections_dict[crn] = seats

    def _switch_to_disabled_tab(self):
        """Switch to the disabled tab if it exists.

        Returns:
            True if switched successfully, False otherwise
        """
        try:
            disabled_tabs = self.driver.find_elements(
                By.XPATH, '//*[@id="scheduler-app"]/div/main/div/div/div[2]/ul/li[2]/a/span'
            )

            if disabled_tabs:
                disabled_tabs[0].click()
                # Wait for the content to load (should load instantly)
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CLASS_NAME, 'css-1p12g40-cellCss-hideOnMobileCss'))
                )
                return True
            else:
                print("Disabled tab does not exist, check for an invalid CRN input.")
                return False
        except Exception as e:
            print(f"Error switching to disabled tab: {e}")
            return False

    def check_sections(self, current_link: str):
        """Check for section availability changes and send notifications.
        This method also handles refreshing for any page errors.

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
                # In the case that there are no sections, could be errored or could have no sections
                if self.has_no_sections():
                    return
                    # Break and don't toggle success to True if errored

                # Otherwise refresh and retry because it's just a page error or a timeout
                self.driver.get(current_link)

        # At this point, success is True (there are sections to check), or we returned early.
        # Extract section information from the enabled tab
        try:
            self._extract_sections(visible_sections)
        except Exception as e:
            print(f"Error extracting sections: {e}")
            return

        # Keep track of CRNs that haven't been found yet
        missing_crns = []

        # Store current sections to update after all notifications are sent
        sections_to_update = []

        # Process all sections from the current tab
        for webhook, classes in self.data.items():
            # Skip if the user has reached their stop time
            if self._user_past_stop_time(webhook):
                continue

            # Check every section
            for section in classes:
                # Skip if the course doesn't match the current one
                if section["course"] != current_course:
                    continue

                crn = section["crn"]

                # Handle sections that are currently visible
                if crn in visible_sections:
                    prev_seats = self.section_states[current_course].get(crn, None)
                    current_seats = visible_sections[crn]

                    # Send notification if needed
                    self._send_section_notification(
                        webhook, section, current_course, crn,
                        prev_seats, current_seats
                    )

                    # Add to list of sections to update
                    sections_to_update.append((webhook, crn, current_seats))
                else:
                    # Keep track of CRNs that weren't found
                    missing_crns.append((webhook, section))

        # If there are missing CRNs, check the "Disabled" tab
        if missing_crns and self._switch_to_disabled_tab():
            # Extract sections from the disabled tab
            disabled_sections = {}
            try:
                self._extract_sections(disabled_sections)
            except Exception as e:
                print(f"Error extracting sections from disabled tab: {e}")
                return

            # Process the sections from the disabled tab
            for webhook, section in missing_crns:
                crn = section["crn"]

                if crn in disabled_sections:
                    prev_seats = self.section_states[current_course].get(crn, None)
                    current_seats = disabled_sections[crn]

                    # Send notification if needed
                    self._send_section_notification(
                        webhook, section, current_course, crn,
                        prev_seats, current_seats
                    )

                    # Add to list of sections to update
                    sections_to_update.append((webhook, crn, current_seats))
                else:
                    # Likely invalid CRN input
                    print(
                        f"CRN {crn} not found in {current_course} visible or disabled sections, check for an invalid CRN input.")

        # Update all sections after processing notifications
        processed_crns = set()
        for webhook, crn, current_seats in sections_to_update:
            # Update in-memory state only once per CRN
            if crn not in processed_crns:
                self.section_states[current_course][crn] = current_seats
                processed_crns.add(crn)

            # Always update database for each webhook-CRN combination
            self._update_course_seat_count(webhook, crn, current_seats)

    def _send_section_notification(self, webhook, section, course, crn, prev_seats, current_seats):
        """Determine if a notification should be sent for a section change and send it if needed.

        Args:
            webhook: The webhook URL to send notifications to
            section: The section data from configuration
            course: The course name
            crn: The Course Registration Number
            prev_seats: Previous seat count (or None if first check)
            current_seats: Current seat count
        """
        # Get the last known seat count from DB
        last_seat_count = section.get("last_seat_count")

        # Check if this is the first time seeing this section
        if prev_seats is None:
            # Only send notification if we have no record in DB or DB value differs from current
            if (last_seat_count is None or last_seat_count != current_seats) and current_seats > 0:
                prof = section["prof"]

                status = f'Seats Available ({current_seats})'

                message = (
                    f'{course} with {prof} is available.\n'
                    f'CRN: {crn}\n'
                    f'Aggie Schedule Builder: {FALL_2025_URL}'
                )

                self._send_notification(webhook, status, message)
        else:
            # We've seen this section before in this session
            # Normal operation: send notification when seat count changes.
            if prev_seats != current_seats:
                prof = section["prof"]

                status = f'Seat Change: {prev_seats} → {current_seats}'

                message = (
                    f'{course} with {prof} is available.\n'
                    f'CRN: {crn}\n'
                    f'Aggie Schedule Builder: {FALL_2025_URL}'
                )

                # Alternative message
                if current_seats == 0:
                    status = "Section Full"
                    message = f'{course} with {prof} is now full.\nCRN: {crn}'

                self._send_notification(webhook, status, message)

    def _send_notification(self, webhook: str, title: str, description: str):
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

        # Changed from while True to check termination event
        while not termination_event.is_set():
            # Check for new courses every cycle
            self.check_for_new_courses()

            # PHASE 1: Refresh all tabs first
            for window_handle in list(self.driver.window_handles):
                if termination_event.is_set():
                    break

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
                    if self.redirect_if_invalid():
                        # If we redirected, the page is already fresh
                        pass
                    else:
                        # Reload page fully
                        self.driver.get(current_link)

                except NoSuchWindowException:
                    # Remove this handle from our tracking
                    if window_handle in self.tab_links:
                        del self.tab_links[window_handle]
                except WebDriverException:
                    pass
                except Exception:
                    traceback.print_exc()
                    pass

            # PHASE 2: Now check each tab for section changes
            for window_handle in list(self.driver.window_handles):
                if termination_event.is_set():
                    break

                try:
                    self.driver.switch_to.window(window_handle)

                    # Skip invalid pages
                    if "offscreen_compiled.js" in self.driver.page_source:
                        continue

                    current_link = self.tab_links.get(window_handle)
                    if current_link:
                        # One last invalid page check
                        self.redirect_if_invalid()
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


# Run the monitor in a thread
def run_monitor():
    try:
        monitor = HowdySeek()
        monitor.run()
    except Exception as e:
        print(f"Monitor error: {e}")
        traceback.print_exc()
        termination_event.set()


# Run Discord bot in a thread
def run_discord_bot():
    try:
        intents = discord.Intents.default()
        client = discord.Client(intents=intents)

        @client.event
        async def on_ready():
            client.loop.create_task(check_termination())
            client.loop.create_task(update_status())

        async def check_termination():
            while not termination_event.is_set():
                await asyncio.sleep(1)
            await client.close()

        # Updates the Discord Presence
        async def update_status():
            while not termination_event.is_set():
                try:
                    response = requests.get(f"{API_BASE_URL}/users/")
                    if response.status_code == 200:
                        users = response.json()

                        # Count active users and total courses
                        active_users = len(users)
                        total_courses = 0

                        for user in users:
                            total_courses += len(user['courses'])

                        courses_text = "CRN" if total_courses == 1 else "CRNs"
                        users_text = "user" if active_users == 1 else "users"

                        # Set the custom activity
                        activity = discord.Activity(
                            name=f"{total_courses} {courses_text} for {active_users} {users_text} 😛",
                            type=discord.ActivityType.watching
                        )
                        await client.change_presence(activity=activity)

                except Exception:
                    traceback.print_exc()

                # Update every 5 minutes
                await asyncio.sleep(300)

        client.run(os.getenv("DISCORD_TOKEN"))
    except Exception as e:
        print(f"Discord bot error: {e}")
        traceback.print_exc()
        termination_event.set()


if __name__ == "__main__":
    try:
        # Set up signal handling
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Create and start threads
        monitor_thread = threading.Thread(target=run_monitor)
        discord_thread = threading.Thread(target=run_discord_bot)

        monitor_thread.start()
        discord_thread.start()

        # Wait for threads to terminate
        monitor_thread.join()
        discord_thread.join()

        print("Program terminated")
    except Exception as e:
        print(f"Main program error: {e}")
        traceback.print_exc()
        sys.exit(1)
