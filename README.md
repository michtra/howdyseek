# howdyseek
the #1 solution to getting the classes you need. created just in time for spring 2025 open registration.

bulletproof and ready with a frontend for fall 2025 preregistration + open registration.

howdyseek (aka michaelseek) > all

dropping your course is NO LONGER safe ❌

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
- Q: Why is the name of this 'howdyseek (하우디 시크)?'
- A: in honor of my permanent IP ban from howdy.tamu.edu and compass-ssb.tamu.edu (those who know 💀💀💀) (don't self-host [better-aggieseek](https://github.com/michtra/better-aggieseek) 💀💀💀💀)

- Q: Is howdyseek bulletproof
- A: yuh

- Q: is howdyseek really that good?
- A: yes. proof below

Proof: Assume, for the sake of contradiction, that HowdySeek is not the best course seat tracker. Then there must exist some tracker X such that X is better than HowdySeek. However, by the definition of HowdySeek, for all trackers X, HowdySeek is literally the best. This contradicts the assumption that such an X exists.

Therefore, our assumption must be false, and HowdySeek is indeed the best course seat tracker. Q.E.D.

# Database Schema
The database schema can be found [here.](SCHEMA.md)

# Wins
See our win count [here.](WINS.md)

# Setup
See the installation guide [here.](INSTALLATION.md)
