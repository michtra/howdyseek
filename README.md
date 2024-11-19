# howdyseek
the #1 solution to getting the classes you need. created just in time for spring 2025 open registration.

howdyseek > all

# Description
This program uses Selenium to loop through your added courses on Aggie Schedule Builder and clicks on each one's information
regarding sections with available seats to notify you through a Discord webhook.

Firstly, it creates a tab for each course you want to track. Then it loops through each tab, refreshes to find the
number of seats, and notifies you accordingly.

## Notes
Originally I tried accessing just the page
links (https://tamu.collegescheduler.com/terms/Spring%202025%20-%20College%20Station/courses/...) but Schedule Builder
forces me to choose the term. I also tried accessing the course page after choosing the term, but Schedule Builder forces
a term selection again. Therefore, the term has to be selected on the initial page and there's no workaround.

# NFAQ (non-frequently asked questions)
- Q: Why is the name of this 'howdyseek?'
- A: in honor of my permanent IP ban from howdy.tamu.edu and compass-ssb.tamu.edu (those who know 💀💀💀) (don't self-host [better-aggieseek](https://github.com/michtra/better-aggieseek) 💀💀💀💀)

- Q: is howdyseek really that good?
- A: yes

# Setup
- Install requirements from requirements.txt (`pip install -r requirements.txt`)
- Modify config-example.json to have a discord webhook point to an array of sections
- Rename config-example.json to config.json

## Browser setup (Chrome/Chromium)
- Have a user profile with cookies enabled
- Log in to your university account
- Navigate to chrome://profile-internals/ to find the correct Profile Path
- Ensure the correct user data directory and profile is set in `main.py`
- Add all the courses you want to track to Aggie Schedule Builder

# Usage
- Make sure you don't have another instance of Chromium open
- Run the python script
