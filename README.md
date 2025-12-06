# AnimePahe Auto Downloader

This project is a Python script that automates downloading anime episodes from AnimePahe. It uses Selenium to control a web browser, navigate the website, and download episodes based on user input.

## Features

-   Download a range of episodes for a specific anime.
-   Select the desired download quality.
-   Automatically handles different download providers (Kwik, Uqload).
-   Includes an adblocker to prevent pop-ups and ads.
-   Saves screenshots of errors for debugging.

## Prerequisites

-   Python 3.x
-   Node.js & NPM
-   Google Chrome browser

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/animepahe-auto-downloader.git
    cd animepahe-auto-downloader
    ```

2.  **Install dependencies:**
    ```bash
    npm install
    npm run setup
    ```

## Usage

**Start the application:**
```bash
npm run dev
```
This will start both the backend API and the frontend interface. Open the URL shown in the terminal (usually `http://localhost:5173`).

## Development

-   **Backend:** `web/main.py` (FastAPI)
-   **Frontend:** `frontend/` (Vite + Vanilla JS)

To build for production:
```bash
npm run build
```

## Disclaimer

This script is for educational purposes only. Please respect the terms of service of the websites you visit. The developers of this script are not responsible for any misuse of this tool.