# howdyseek
the #1 solution to getting the classes you need. created just in time for spring 2025 open registration.

howdyseek (aka michaelseek) > all

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

# Database Schema
## Settings
- id (PK): Integer
- min_refresh_interval: Float (Default: 30.0)
- max_refresh_interval: Float (Default: 40.0)

## Users
- id (PK): Integer
- name: String
- webhook_url: String (Discord webhook URL for notifications)

## Courses
- id (PK): Integer
- course_name: String
- professor: String
- crn: String
- user_id (FK): Integer (References users.id)

# NFAQ (non-frequently asked questions)
- Q: Why is the name of this 'howdyseek (하우디 시크)?'
- A: in honor of my permanent IP ban from howdy.tamu.edu and compass-ssb.tamu.edu (those who know 💀💀💀) (don't self-host [better-aggieseek](https://github.com/michtra/better-aggieseek) 💀💀💀💀)

- Q: Is howdyseek bulletproof
- A: yuh

- Q: is howdyseek really that good?
- A: yes. proof below

Proof: Assume, for the sake of contradiction, that HowdySeek is not the best course seat tracker. Then there must exist some tracker X such that X is better than HowdySeek. However, by the definition of HowdySeek, for all trackers X, HowdySeek is literally the best. This contradicts the assumption that such an X exists.

Therefore, our assumption must be false, and HowdySeek is indeed the best course seat tracker. Q.E.D.

## Current howdyseek W count: 12
1. STAT 212 with Patricia Ning (11am section > all)
2. CSCE 221 with Beideman (Beideman the GOAT)
3. ECEN 214 with Butler-Parry Karen (ECEN majors just can't compete with howdyseek)
4. PBSI 235 with Madison (Neuroscience lovers just can't compete with howdyseek)
5. STAT 211 with Crawford (Web-based W with the GOAT)
6. STAT 211 with Crawford (Another Web-based W with the GOAT) (2x)
7. CSCE 312 with TYAGI (CS majors just can't compete with howdyseek) (Web-based W)
8. PBSI 107 with Hull (Psychology lovers just can't compete with howdyseek) (Web-based W)
9. ENGL 210 with Anders (Average aggie university requirement just can't compete with howdyseek) (Web-based W)
10. CSCE 120 with Merchant (Merchant also goated)
11. CSCE 313 with Kebo (successful add/drop week snipe)
12. Most notable win: POLS 207 with JESSE ALLEN CHUPP (GOAT OF ALL GOATS)

# Setup
See the installation guide [here.](INSTALLATION.md)
