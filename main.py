# Animepahe Auto Downloader v2.2 (Revised - No FDM)
# Automated Anime Downloading from the Animepahe Website Using Selenium Python
# Created by: Jookie262
# Revised by: AI Assistant based on user feedback

# Import Libraries
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
import re
import time
import os # For creating directory for screenshots and downloads
import traceback # For detailed error printing

# --- Configuration ---
DEFAULT_WAIT_TIME = 15 # Increased default wait time
SCREENSHOT_DIR = "error_screenshots"
# Define where downloads should go. Creates 'anime_downloads' subdir in script's directory.
# You can change this to an absolute path like: r"C:\Users\YourUser\Downloads\Anime"
DOWNLOAD_DIR = os.path.join(os.getcwd(), "anime_downloads")
# --- !!! IMPORTANT: SET PATH TO YOUR AD BLOCKER .crx FILE !!! ---
# --- Make sure the file exists at this location ---
# --- Example: Place ublock_origin.crx in the same folder as the script ---
# AD_BLOCKER_PATH = os.path.join(os.getcwd(), "uBlock0.chromium.crx") # Adjust filename if needed
# AD_BLOCKER_UNPACKED_PATH = os.path.join(os.getcwd(), "uBlock0.chromium") # Adjust folder name if needed

AD_BLOCKER_PATH = os.path.join(os.getcwd(), "Adblock-Plus.crx") # Adjust filename if needed
AD_BLOCKER_UNPACKED_PATH = os.path.join(os.getcwd(), "Adblock-Plus") # Adjust folder name if needed


# Create screenshot directory if it doesn't exist
if not os.path.exists(SCREENSHOT_DIR):
    os.makedirs(SCREENSHOT_DIR)
    print(f"Created directory: {SCREENSHOT_DIR}")

# Create download directory if it doesn't exist
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)
    print(f"Created directory: {DOWNLOAD_DIR}")
print(f"Downloads will be saved to: {DOWNLOAD_DIR}")


def save_debug_info(driver, error_name):
    """Saves screenshot for debugging."""
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    screenshot_path = os.path.join(SCREENSHOT_DIR, f"error_{error_name}_{timestamp}.png")
    try:
        driver.save_screenshot(screenshot_path)
        print(f"Screenshot saved to: {screenshot_path}")
    except Exception as e:
        print(f"Could not save debug info: {e}")

# --- User Input ---
anime = input("Enter the name of the anime: ")
pixels = input("Enter the quality of the video (e.g., 720 or 1080): ")
start_ep_input = input("Enter the episode number to start from (hit enter to start from 1): ")
start_ep = 1 if start_ep_input.strip() == '' else int(start_ep_input)
end_ep_input = input("Enter the episode number to end at (hit enter to end at the latest): ")
# end_ep will be determined later if empty

# --- Setup Chrome Driver ---
options = webdriver.ChromeOptions()
options.add_argument("start-maximized")
# options.add_argument("--headless") # Optional: Run in background
# options.add_argument("--disable-gpu") # Often needed with headless

# Configure Chrome preferences for direct downloads
prefs = {
    "download.default_directory": DOWNLOAD_DIR, # Set download directory
    "download.prompt_for_download": False,  # Disable "Save As" dialog
    "download.directory_upgrade": True,     # Allow download directory management
    "safebrowsing.enabled": True,           # Enable safe browsing checks
    "extensions.ui.developer_mode": True
}
options.add_experimental_option("prefs", prefs)
# options.add_experimental_option('excludeSwitches', ['enable-logging']) # May hide useful info

options.add_extension(AD_BLOCKER_PATH)


# # --- !!! Load Ad Blocker as Unpacked Extension !!! ---
# if os.path.isdir(AD_BLOCKER_UNPACKED_PATH) and os.path.exists(os.path.join(AD_BLOCKER_UNPACKED_PATH, 'manifest.json')):
#     print(f"Attempting to load unpacked extension from: {AD_BLOCKER_UNPACKED_PATH}")
#     # Use add_argument with --load-extension=PATH
#     options.add_argument(f"--load-extension={AD_BLOCKER_UNPACKED_PATH}")
#     print("Unpacked ad blocker extension specified.")
#     # Keep the delay after driver start to allow initialization
# else:
#     print(f"Warning: Unpacked ad blocker directory not found or invalid at {AD_BLOCKER_UNPACKED_PATH}")
#     print("Proceeding without ad blocker. Redirects/ads might cause issues.")

# # --- Add Ad Blocker Extension ---
# if os.path.exists(AD_BLOCKER_PATH):
#     print(f"Attempting to load extension: {AD_BLOCKER_PATH}")
#     try:
#         options.add_extension(AD_BLOCKER_PATH)
#         print("Ad blocker extension added.")
#         # Extensions might take a moment to load after browser starts
#         time.sleep(5) # Add a small delay after driver starts later
#     except Exception as e:
#         print(f"Warning: Could not load extension from {AD_BLOCKER_PATH}. Error: {e}")
#         print("Proceeding without ad blocker. Redirects/ads might cause issues.")
# else:
#     print(f"Warning: Ad blocker extension not found at {AD_BLOCKER_PATH}")
#     print("Proceeding without ad blocker. Redirects/ads might cause issues.")

# --- REMOVED FDM EXTENSION LOADING ---
# try:
#     options.add_extension('fdm.crx')
# except Exception as e:
#     print(f"Warning: Could not load fdm.crx extension...")

try:
    print("Setting up Chrome Driver...")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    actionChains = ActionChains(driver)
    print("Driver setup complete.")
except Exception as e:
    print(f"Fatal Error: Failed to initialize Chrome Driver: {e}")
    print("Please ensure Chrome is installed and webdriver-manager can download the driver.")
    exit()




# --- Main Script Logic ---
try:
    # Open Animepahe Website
    print(f"Navigating to Animepahe...")
    driver.get("https://animepahe.com/") # Use .com, though it might redirect
    time.sleep(2) # Allow initial page load/redirects
    # Type the anime text in the search bar
    print(f"Searching for anime: {anime}")
    try:
        search_box = WebDriverWait(driver, DEFAULT_WAIT_TIME).until(
            EC.presence_of_element_located((By.NAME, "q"))
        )
        search_box.send_keys(anime)
        time.sleep(0.3) # Small pause allows JS to potentially react to initial input
        search_box.send_keys(Keys.BACKSPACE)
        time.sleep(0.1) # Tiny pause
        # Send the last character of the original anime name string
        search_box.send_keys(anime[-1])
        print(f"Typed '{anime}', backspaced, retyped last character ('{anime[-1]}').")
        time.sleep(0.5) # Give a moment for results to potentially update before hitting Enter
        print("Search submitted.")
    except TimeoutException:
        print("Error: Could not find the search bar (By.NAME, 'q'). Website structure might have changed.")
        save_debug_info(driver, "search_bar_not_found")
        driver.quit()
        exit()

    # Click the first element in the result
    print("Looking for search results...")
    try:
        # INSPECT the site structure for the correct selector!
        # Examples: 'search-results', 'p-search-results', 'results-container'
        search_results_container = WebDriverWait(driver, DEFAULT_WAIT_TIME).until(
             EC.presence_of_element_located((By.CLASS_NAME, "search-results"))
        )
        # Find the first link within the results container
        first_result_link = WebDriverWait(search_results_container, DEFAULT_WAIT_TIME).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "li > a")) # Assumes li > a structure
        )
        print(f"Found first result: {first_result_link.text}. Clicking...")
        first_result_link.click()
    except TimeoutException:
        print(f"Error: Anime '{anime}' not found or search results structure changed.")
        save_debug_info(driver, "anime_not_found")
        driver.quit()
        exit()
    except Exception as e:
        print(f"An unexpected error occurred while clicking search result: {e}")
        save_debug_info(driver, "search_result_click_error")
        driver.quit()
        exit()
    time.sleep(3)
    # Get the total number of Anime Episodes
    print("Fetching total episode count...")
    try:
        # --- !!! UPDATE THIS SELECTOR BASED ON INSPECTION !!! ---
        # Example: Find the container first, then extract text
        details_container = WebDriverWait(driver, DEFAULT_WAIT_TIME).until(
            # Option 1: If a specific container exists
    #----------------------------------------------------------------------------------------------------------------spot where error
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.anime-info"))
            # Option 2: A different class name you might find
            # EC.presence_of_element_located((By.CLASS_NAME, "anime-details"))
            # Option 3: If it's within a specific header/section
            # EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'header')]/p"))
        )
        details_text = details_container.text
        print(f"Found details text block: '{details_text[:100]}...'") # Print start of text for debug

        # Try to extract the number more robustly
        # Look for "NN Episodes" first
        match = re.search(r'(\d+)\s+Episodes', details_text, re.IGNORECASE)
        if not match:
             # Fallback: Look for just digits if the pattern above fails
             print("Could not find 'NN Episodes' pattern, searching for any digits...")
             match = re.search(r'(\d+)', details_text)

        if match:
            num_episode_total = int(match.group(1))
            print(f"Successfully extracted total episodes: {num_episode_total}")
        else:
            print(f"Warning: Could not extract episode number from text: '{details_text}'")
            save_debug_info(driver, "episode_count_parsing_failed")
            num_episode_total = 0 # Set a default

        # --- Rest of the logic ---
        if num_episode_total == 0 and end_ep_input.strip() == '':
             print("Error: Could not determine total episodes and no end episode specified. Please check the selectors or specify an end episode.")
             driver.quit()
             exit()

        end_ep = num_episode_total if end_ep_input.strip() == '' else int(end_ep_input)
        print(f"Targeting episodes from {start_ep} to {end_ep}.")

    except TimeoutException:
        # This error means the container selector itself failed
        print("Error: Could not find the element/container holding the episode count. Page structure likely changed.")
        print(">>> Please inspect the anime page on Animepahe manually and update the CSS_SELECTOR/XPATH in the script.")
        save_debug_info(driver, "episode_count_container_not_found")
        driver.quit()
        exit()
    except Exception as e:
        print(f"An unexpected error occurred while getting episode count: {e}")
        traceback.print_exc() # Print full traceback for unexpected errors
        save_debug_info(driver, "episode_count_error")
        driver.quit()
        exit()

    # Navigate to the *player page* of the *starting* episode first.
    print(f"Navigating to starting episode: {start_ep}...")
    try:
        # INSPECT the site structure for the correct selector!
        # Example: 'episode-list-wrapper', '.episodes-container'
        episode_list_container = WebDriverWait(driver, DEFAULT_WAIT_TIME).until(
            EC.presence_of_element_located((By.CLASS_NAME, "episode-list-wrapper"))
        )
        # Find link by partial href (usually more stable)
        start_episode_link = WebDriverWait(episode_list_container, DEFAULT_WAIT_TIME).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, f"a[href*='/{start_ep}']")) # Matches href containing /N
        )
        print(f"Found link for episode {start_ep}. Clicking...")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", start_episode_link)
        time.sleep(0.5)
        start_episode_link.click()
        print("Navigated to player page for starting episode.")
        time.sleep(3)

    except TimeoutException:
        print(f"Error: Could not find or click the link for starting episode {start_ep}.")
        print("Check if the episode exists and if the selectors for episode list/links are correct.")
        save_debug_info(driver, f"start_episode_{start_ep}_not_found")
        driver.quit()
        exit()
    except ElementClickInterceptedException:
         print(f"Error: Clicking starting episode {start_ep} link was intercepted (likely by an ad/overlay).")
         save_debug_info(driver, f"start_episode_{start_ep}_intercepted")
         try:
             print("Retrying click with JavaScript...")
             driver.execute_script("arguments[0].click();", start_episode_link)
             print("Navigated to player page for starting episode using JavaScript click.")
             time.sleep(3)
         except Exception as js_e:
             print(f"JavaScript click also failed: {js_e}")
             driver.quit()
             exit()
    except Exception as e:
        print(f"An unexpected error occurred navigating to the starting episode: {e}")
        save_debug_info(driver, f"start_episode_{start_ep}_error")
        driver.quit()
        exit()


    # --- Loop Through Episodes ---
    current_ep = start_ep
    while current_ep <= end_ep:
        print(f"\n--- Processing Episode {current_ep} ---")

        try:
            # Click the download button/menu
            print("Clicking download menu...")
            # INSPECT site for correct ID/selector
            download_menu_button = WebDriverWait(driver, DEFAULT_WAIT_TIME).until(
                EC.element_to_be_clickable((By.ID, "downloadMenu"))
            )
            download_menu_button.click()
            time.sleep(1)

            # Find and click the desired quality link
            print(f"Selecting quality: {pixels}p...")
            # INSPECT site for correct ID/selector
            download_options_container = WebDriverWait(driver, DEFAULT_WAIT_TIME).until(
                EC.visibility_of_element_located((By.ID, "pickDownload"))
            )
            quality_link = WebDriverWait(download_options_container, DEFAULT_WAIT_TIME).until(
                EC.element_to_be_clickable((By.XPATH, f".//a[contains(text(), '{pixels}p')]"))
            )
            print(f"Found quality link: {quality_link.text}. Clicking...")
            try:
                quality_link.click()
            except ElementClickInterceptedException:
                print("Quality link click intercepted, trying JavaScript click...")
                driver.execute_script("arguments[0].click();", quality_link)

            time.sleep(2)

            # --- Handle Pahewin/Download Page ---
            print("Switching to download page (Pahewin/other)...")
            if len(driver.window_handles) < 2:
                print("Error: New download window/tab did not open.")
                save_debug_info(driver, f"ep_{current_ep}_no_new_window")
                print(f"Skipping episode {current_ep} due to download window issue.")
                # Need robust logic to advance to next episode if possible
                current_ep += 1 # Tentative increment
                continue

            driver.switch_to.window(driver.window_handles[-1])
            print(f"Current URL: {driver.current_url}")

            # Handle potential intermediate pages (like Pahewin 'Continue')
            pahewin_continue_attempts = 3
            for attempt in range(pahewin_continue_attempts):
                try:
                    # INSPECT site for 'Continue' button selector
                    continue_button = WebDriverWait(driver, 10).until(
                         EC.element_to_be_clickable((By.LINK_TEXT, "Continue"))
                    )
                    print("Found 'Continue' button, clicking...")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", continue_button)
                    time.sleep(0.5)
                    continue_button.click()
                    print("'Continue' button clicked.")
                    time.sleep(3) # Wait for next page
                    break
                except TimeoutException:
                    print(f"'Continue' button not found on attempt {attempt + 1}/{pahewin_continue_attempts}.")
                    if attempt == pahewin_continue_attempts - 1:
                         print("Proceeding, assuming we are on the final download page.")
                    time.sleep(1)
                except Exception as e:
                    print(f"Error clicking 'Continue' button: {e}")
                    save_debug_info(driver, f"ep_{current_ep}_continue_error")
                    break


            # Handle the final download page (e.g., Kwik)
            kwik_download_attempts = 3
            download_started = False
            for attempt in range(kwik_download_attempts):
                 time.sleep(2)
                 print(f"Looking for final download button (Attempt {attempt+1})...")
                 print(f"Current URL (final page check): {driver.current_url}")
                 try:
                     # INSPECT Kwik/hoster page for the correct download button selector
                     final_download_button = WebDriverWait(driver, 20).until(
                         EC.element_to_be_clickable((By.CSS_SELECTOR, "form button[type='submit']"))
                     )
                     print("Found final download button. Clicking...")
                     driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", final_download_button)
                     time.sleep(0.5)

                     final_download_button.click()
                     # Download should now start via Chrome's manager
                     print(f"Download initiated for Episode {current_ep} (check browser downloads in '{DOWNLOAD_DIR}').")
                     download_started = True
                     # Allow some time for the download to actually begin before closing the tab
                     time.sleep(5) # Adjust if downloads seem to be cut off
                     break

                 except TimeoutException:
                     print("Final download button not found or not clickable.")
                     save_debug_info(driver, f"ep_{current_ep}_kwik_btn_timeout_attempt_{attempt+1}")
                     if attempt < kwik_download_attempts - 1:
                          print("Refreshing page and retrying...")
                          driver.refresh()
                          time.sleep(3)
                     else:
                          print(f"Failed to find/click final download button after {kwik_download_attempts} attempts.")
                 except ElementClickInterceptedException:
                      print("Final download button click intercepted. Trying JS click...")
                      try:
                           driver.execute_script("arguments[0].click();", final_download_button)
                           print(f"Download initiated for Episode {current_ep} using JS click (check browser downloads in '{DOWNLOAD_DIR}').")
                           download_started = True
                           time.sleep(5)
                           break
                      except Exception as js_e:
                           print(f"JS click also failed: {js_e}")
                           save_debug_info(driver, f"ep_{current_ep}_kwik_btn_js_fail")
                 except Exception as e:
                     print(f"An unexpected error occurred on the final download page: {e}")
                     save_debug_info(driver, f"ep_{current_ep}_kwik_error")
                     break

            # Close the download tab and switch back
            print("Closing download tab...")
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
            time.sleep(1)

            if not download_started:
                print(f"Warning: Download for episode {current_ep} may not have started. Skipping.")
                # Decide how to proceed - skipping is simplest here

            # Navigate to the next episode (if not the last one)
            if current_ep < end_ep:
                print(f"Navigating to next episode ({current_ep + 1})...")
                try:
                    # INSPECT player page for 'Next' button selector
                    next_episode_button = WebDriverWait(driver, DEFAULT_WAIT_TIME).until(
                        EC.element_to_be_clickable((By.XPATH, "//a[contains(@title, 'Next Episode')]"))
                    )
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_episode_button)
                    time.sleep(0.5)
                    driver.execute_script("arguments[0].click();", next_episode_button)
                    print("Clicked 'Next Episode' button.")
                    time.sleep(3) # Wait for next episode's player page to load
                    current_ep += 1
                except TimeoutException:
                    print(f"Error: Could not find or click the 'Next Episode' button after episode {current_ep}.")
                    save_debug_info(driver, f"ep_{current_ep}_next_button_timeout")
                    print("Stopping script as next episode navigation failed.")
                    break
                except Exception as e:
                    print(f"An unexpected error occurred clicking 'Next Episode': {e}")
                    save_debug_info(driver, f"ep_{current_ep}_next_button_error")
                    break
            else:
                print("Reached the target end episode.")
                break # Exit loop

        except TimeoutException as e:
            print(f"Timeout Error processing episode {current_ep}: {e}")
            save_debug_info(driver, f"ep_{current_ep}_timeout_error")
            print("Attempting to recover or skipping episode.")
            if current_ep < end_ep:
                 print(f"Attempting to recover by navigating to episode {current_ep + 1}")
                 try:
                    # Try clicking next button again
                    next_episode_button = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.episodeNext")))
                    driver.execute_script("arguments[0].click();", next_episode_button)
                    time.sleep(3)
                    current_ep += 1
                 except Exception:
                    print("Recovery failed. Stopping.")
                    break
            else:
                 break # Already at end episode

        except Exception as e:
            print(f"An unexpected error occurred while processing episode {current_ep}: {e}")
            traceback.print_exc() # Print full traceback for unexpected errors
            save_debug_info(driver, f"ep_{current_ep}_unexpected_error")
            print("Stopping script due to unexpected error.")
            break


except Exception as e:
    print(f"\n--- A critical error occurred in the main script execution ---")
    print(f"Error: {e}")
    traceback.print_exc() # Print detailed traceback
    if 'driver' in locals() and driver:
        save_debug_info(driver, "critical_failure")

finally:
    if 'driver' in locals() and driver:
        print("\nScript finished or terminated. Closing browser.")
        driver.quit()
    else:
        print("\nScript terminated before driver initialization.")

print(f"Finish Downloading (or script ended). Check the '{DOWNLOAD_DIR}' folder and your browser's download history.")