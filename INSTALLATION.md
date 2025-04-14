# Installation Guide
This contains the installation instructions for the backend and frontend.

## Backend setup
- `cd howdyseek-backend`
- Install requirements from requirements.txt
  - `pip install -r requirements.txt`
- Start the API server
  - `uvicorn api:app --reload --log-level critical --host 0.0.0.0 --port 8000`

### Discord Bot Status
- Create a Discord bot (https://discord.com/developers/docs/intro)
- Get its token, place it in `.env.example`, rename to `.env`
- This Discord bot will be used to show the running status of howdyseek

## Browser setup (Chrome/Chromium)
- Have a user profile with cookies enabled
- Log in to your university account
- Navigate to `chrome://profile-internals/` to find the correct Profile Path
- Ensure the correct user data directory and profile is set in `backend/main.py`
- Add all the courses you want to track to Aggie Schedule Builder
- In Schedule Builder, change Course Status to `Open & Full` to see full classes as well.

## Frontend setup
  - `cd howdyseek-frontend`
  - `npm install`
  - `npm start`
  - Since the backend doesn't work with an existing instance of Chromium, I use the frontend on a different browser.
    - Navigate to `localhost:3000` on the other browser after compiling the React application
 
## Running the course tracker
- Make sure you don't have another instance of Chromium open
- The script **will not work properly** if the Chromium window is not fully expanded (doesn't have to be focused/in view though, just maximized)
  - This is because when not fully zoomed in, the tab creation does not correctly find courses
  - The current implementation takes care of this already and fully expands the window.
- Run the python script after setting up users and courses through the frontend
  - `python backend/main.py`

## Adding courses
As a prerequisite to adding a course to track, ensure the course is added to Schedule Builder.

## Stop time
If a user is past their stop time for tracking and the application is restarted, then there will not be tabs created for their course.
