# Installation Guide
This contains the installation instructions for the backend and frontend.

## Backend setup
- `cd howdyseek-backend`
- Install requirements from requirements.txt
  - `pip install -r requirements.txt`
- Start the API server
  - `uvicorn api:app --reload --host 0.0.0.0 --port 8000`

## Browser setup (Chrome/Chromium)
- Have a user profile with cookies enabled
- Log in to your university account
- Navigate to `chrome://profile-internals/` to find the correct Profile Path
- Ensure the correct user data directory and profile is set in `backend/main.py`
- Add all the courses you want to track to Aggie Schedule Builder

## Frontend setup
  - `cd howdyseek-frontend`
  - `npm install`
  - `npm start`
  - Since the backend doesn't work with an existing instance of Chromium, I use the frontend on a different browser.
 
## Running the course tracker
- Make sure you don't have another instance of Chromium open
- The script **will not work properly** if the Chromium window is not fully expanded (doesn't have to be focused/in view though, just maximized)
  - This is because when not fully zoomed in, the tab creation does not correctly find courses
- Run the python script after setting up users and courses through the frontend
  - `python backend/main.py`
