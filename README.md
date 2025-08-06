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
-   Google Chrome browser

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/animepahe-auto-downloader.git
    cd animepahe-auto-downloader
    ```
2.  **Install the required Python packages:**
    ```bash
    pip install -r requirements.txt
    ```

## Usage

1.  **Run the script:**
    ```bash
    python main.py
    ```
2.  **Follow the on-screen prompts:**
    -   Enter the name of the anime you want to download.
    -   Enter the starting and ending episode numbers.
    -   Choose the download quality (e.g., 720p, 1080p).

The script will then open a Chrome browser window and start downloading the episodes. The downloaded files will be saved in the `anime_downloads` directory.

## Disclaimer

This script is for educational purposes only. Please respect the terms of service of the websites you visit. The developers of this script are not responsible for any misuse of this tool.