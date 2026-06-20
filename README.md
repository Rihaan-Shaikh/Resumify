# Resumify
[![Ask DeepWiki](https://devin.ai/assets/askdeepwiki.png)](https://deepwiki.com/Rihaan-Shaikh/Web-Dev/tree/main/Resumify)

Resumify is a sophisticated AI-powered resume builder designed to help users create professional, impactful resumes. It combines a sleek vanilla JavaScript frontend with a powerful dual-backend architecture: a FastAPI service for real-time AI analysis and a Django service for user authentication and cloud storage.

## Key Features

-   **Dynamic Resume Editor**: Create and edit your resume in a clean user interface with categorized sections for experience, education, projects, and more.
-   **AI-Powered Feedback**: Submit your project descriptions to an AI model that analyzes linguistic strength, provides an overall resume score, and offers suggestions for improvement using a Hugging Face NLP model.
-   **Live LaTeX Preview**: See your resume's LaTeX source code generated in real-time as you type.
-   **User Authentication**: Secure user registration and login system powered by Django and `django-allauth`.
-   **Cloud Storage**: Save multiple resume versions to your account and load them anytime.
-   **Multiple Export Options**: Download your final resume as a `.tex` file, a print-ready PDF, or simply copy the LaTeX source code.
-   **Robust Validation**: The FastAPI backend uses Pydantic to ensure all submitted data is complete and correctly formatted before processing.
-   **Auto-Save Drafts**: Work-in-progress is automatically saved to your browser's local storage, preventing data loss.

## Architecture Overview

Resumify employs a microservices-style architecture with three distinct components:

### 1. Frontend (`/frontend`)

A single-page application built with **vanilla JavaScript, HTML, and CSS**. It provides the complete user interface for editing resume content, viewing AI feedback, managing cloud saves, and initiating downloads. It communicates with the two backend services via API calls.

### 2. AI Backend (`/backend`)

A **FastAPI** application that serves the AI and validation logic.

-   **Data Validation (`POST /resume`)**: Uses Pydantic schemas to validate the incoming resume data, ensuring no fields are empty and data types are correct.
-   **AI Analysis (`POST /analyze`)**: Leverages the `distilbert-base-uncased-finetuned-sst-2-english` sentiment analysis model from Hugging Face Transformers to evaluate the impact of project descriptions. It returns a strength score, confidence level, and actionable suggestions for each project.

### 3. User & Database Backend (`/django_app`)

A **Django** application responsible for user management and data persistence.

-   **Authentication**: Manages user accounts (signup, login, logout) using `django-allauth`.
-   **Database**: Uses a PostgreSQL database to store user credentials and saved resume data.
-   **REST API**: Provides endpoints built with Django REST Framework for authenticated users to save (`/api/save-resume/`) and retrieve (`/api/my-resumes/`) their resumes from the cloud.

## Tech Stack

-   **Frontend**: HTML5, CSS3, Vanilla JavaScript
-   **AI Backend**: FastAPI, Pydantic, Hugging Face Transformers, Uvicorn
-   **User Backend**: Django, Django REST Framework, django-allauth, Psycopg2
-   **Database**: PostgreSQL

## Local Setup and Installation

Follow these steps to run the complete application locally.

### Prerequisites

-   Git
-   Python 3.8+
-   PostgreSQL installed and running.

### 1. Clone the Repository

```bash
git clone https://github.com/rihaan-shaikh/web-dev.git
cd web-dev/Resumify
```

### 2. Configure the Backend

#### a. Create Virtual Environment & Install Dependencies

It's recommended to use a single virtual environment for both backends.

```bash
# Create and activate the virtual environment
python -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`

# Install all required Python packages
pip install -r backend/requirements.txt
```

#### b. Set up the Django (User) Backend

1.  **Create a PostgreSQL Database**:
    -   Create a new database named `resumify_db`.
    -   Update the database credentials (`NAME`, `USER`, `PASSWORD`, `HOST`, `PORT`) in `django_app/core/settings.py` if they differ from the defaults.

2.  **Run Migrations**:
    Navigate to the Django app directory and apply the database schema.
    ```bash
    cd django_app
    python manage.py migrate
    ```

3.  **Run the Django Server**:
    The Django server will handle user authentication and resume storage.
    ```bash
    # Run on port 8001 to avoid conflicts with the FastAPI app
    python manage.py runserver 8001
    ```
    The Django backend is now running at `http://127.0.0.1:8001`.

#### c. Run the FastAPI (AI) Backend

1.  **Navigate to the AI Backend Directory**:
    Open a new terminal, navigate to the project root, activate the virtual environment, and then `cd` into the `backend` directory.

    ```bash
    # From the Resumify root directory
    source venv/bin/activate
    cd backend
    ```

2.  **Run the FastAPI Server**:
    The Uvicorn server will host the AI analysis endpoints. The first time you run this, it will download the Hugging Face model, which may take a few minutes.
    ```bash
    uvicorn main:app --reload --host 127.0.0.1 --port 8000
    ```
    The AI backend is now running at `http://127.0.0.1:8000`.

### 3. Launch the Frontend

Simply open the `frontend/index.html` file in your preferred web browser.

-   For the best experience, use a live server extension (like VS Code's "Live Server") to host the file, which enables features like redirecting back to the app after login.

You can now use the application, create an account, and test all features.

## API Endpoints

### FastAPI Service (`http://127.0.0.1:8000`)

-   `POST /resume`: Validates the structure of the resume JSON payload against the Pydantic schema.
-   `POST /analyze`: Accepts resume data and returns an AI-driven analysis of the project descriptions, including an overall score.

### Django Service (`http://127.0.0.1:8001`)

-   `GET /accounts/login/`: Renders the user login page.
-   `GET /accounts/signup/`: Renders the user signup page.
-   `POST /api/save-resume/`: (Authenticated) Saves the current resume data to the user's account.
-   `GET /api/my-resumes/`: (Authenticated) Retrieves a list of all resumes saved by the user.
-   `GET /api/me/`: (Authenticated) Returns the username of the currently logged-in user.