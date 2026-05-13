# Global-Vessel-Insurance-Agent
Steven Shoemaker and Yoshiki Yamaguchi cause billions of dollars of damage to the world's oceans

## First-Time Setup
The development build of this project has a completely seperate frontend (React x Vite) and backend (Flask). These each have to be setup and installed on their own. For release we can compile the frontend down to plain HTML + JS, but for development purposes we keep the two seperate.

### Setting Up Frontend

1. Install [NodeJS](https://nodejs.org/en)

2. cd `frontend`

3. Run `npm install`

### Setting Up the Backend

Flask is a python program that requires python to run. The project assumes you have miniconda installed and are running all code in a fresh directory.

Currently, the only package the project uses is `Flask`. Realistically, any python environment running version >= 2.6 should run the project just fine.

1. cd `backend`

2. (optional) Create a new environment to run the backend from, `conda create -n insurance_project python=3.12`

3. (optional) Activate that environmentm `conda activate insurance_project`

4. Install flask (if it is not installed already), `pip install flask`

## Running the Project
As the frontend and backend are served seperately, you'll need to use two different terminals to ensure the project works. After both of these steps are taken, you should see a basic test site at `http://localhost:5173/`

### Spin Up the Frontend

1. cd `frontend`

2. `npm run dev`

### Spun Up the Backend

1. cd `backend`

2. `flask run`