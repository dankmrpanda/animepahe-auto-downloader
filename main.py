
import requests
import re
import argparse
import sys
from urllib.parse import unquote

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options 
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm


# --- Configuration ---
DEFAULT_WAIT_TIME = 15
SCREENSHOT_DIR = "error_screenshots"
DOWNLOAD_DIR = os.path.join(os.getcwd(), "anime_downloads")

if not os.path.exists(SCREENSHOT_DIR):
    os.makedirs(SCREENSHOT_DIR)
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

def save_debug_info(driver, error_name):
    """Saves screenshot for debugging."""
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    screenshot_path = os.path.join(SCREENSHOT_DIR, f"error_{error_name}_{timestamp}.png")
    try:
        driver.save_screenshot(screenshot_path)
        print(f"Screenshot saved to: {screenshot_path}")
    except Exception as e:
        print(f"Could not save debug info: {e}")

class KwikPahe:
    def __init__(self):
        self.base_alphabet = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ+/"

    def _0xe16c(self, IS, Iy, ms):
        h = self.base_alphabet[:Iy]
        i = self.base_alphabet[:ms]
        
        j = 0
        for idx, char in enumerate(reversed(IS)):
            pos = h.find(char)
            if pos != -1:
                j += pos * (Iy ** idx)

        if j == 0:
            return i[0]

        k = ""
        while j > 0:
            k = i[j % ms] + k
            j //= ms
        
        return int(k)

    def decode_js_style(self, Hb, Wg, Of, Jg):
        gj = ""
        i = 0
        while i < len(Hb):
            s = ""
            while i < len(Hb) and Hb[i] != Wg[Jg]:
                s += Hb[i]
                i += 1
            
            for j in range(len(Wg)):
                s = s.replace(Wg[j], str(j))

            gj += chr(self._0xe16c(s, Jg, 10) - Of)
            i += 1
        
        return gj

    def fetch_kwik_direct(self, kwik_link, token, kwik_session):
        headers = {
            "referer": kwik_link,
            "cookie": f"kwik_session={kwik_session}",
        }
        data = {"_token": token}
        
        response = requests.post(kwik_link, headers=headers, data=data, allow_redirects=False)
        
        if response.status_code == 302:
            return response.headers.get("Location")
        else:
            raise RuntimeError(f"Redirect Location not found in response from {kwik_link}")

    def fetch_kwik_dlink(self, kwik_link, retries=5):
        if retries <= 0:
            raise RuntimeError("Kwik fetch failed: exceeded retry limit")

        try:
            response = requests.get(kwik_link)
            if response.status_code != 200:
                raise RuntimeError(f"Failed to Get Kwik from {kwik_link}, StatusCode: {response.status_code}")

            clean_text = response.text.replace("\r\n", "").replace("\r", "").replace("\n", "")
            
            kwik_session_match = re.search(r"kwik_session=([^;]*);", response.headers.get("set-cookie", ""))
            kwik_session = kwik_session_match.group(1) if kwik_session_match else ""

            encoded_match = re.search(r'\("([^"]+)",\d+,"([^"]+)",(\d+),(\d+),\d+\)', clean_text)
            if not encoded_match:
                return self.fetch_kwik_dlink(kwik_link, retries - 1)

            encoded_string, alphabet_key, offset, base = encoded_match.groups()
            offset = int(offset)
            base = int(base)

            decoded_string = self.decode_js_style(encoded_string, alphabet_key, offset, base)
            
            link_match = re.search(r'action="([^"]+)"', decoded_string)
            token_match = re.search(r'value="([^"]+)"', decoded_string)

            if not link_match or not token_match:
                return self.fetch_kwik_dlink(kwik_link, retries - 1)

            link = link_match.group(1)
            token = token_match.group(1)
            
            return self.fetch_kwik_direct(link, token, kwik_session)
        except Exception:
            return self.fetch_kwik_dlink(kwik_link, retries - 1)

    def extract_kwik_link(self, session, link):
        response = session.get(link)
        if response.status_code != 200:
            raise RuntimeError(f"Failed to Get Kwik from {link}, StatusCode: {response.status_code}")

        clean_text = response.text.replace("\r\n", "").replace("\r", "").replace("\n", "")
        
        kwik_link = None
        kwik_link_match = re.search(r'(https?://kwik\.[^/\s"]+/[^/\s"]+/[^"\s]*)', clean_text)

        if kwik_link_match:
            kwik_link = kwik_link_match.group(1)
        else:
            encoded_match = re.search(r'\(\s*"([^",]*)"\s*,\s*\d+\s*,\s*"([^",]*)"\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*\d+[a-zA-Z]?\s*\)', clean_text)
            if not encoded_match:
                raise RuntimeError(f"Failed to extract encoding parameters from {link}")
            
            encoded_string, alphabet_key, offset, base = encoded_match.groups()
            offset = int(offset)
            base = int(base)

            decoded_string = self.decode_js_style(encoded_string, alphabet_key, offset, base)
            kwik_link_match = re.search(r'(https?://kwik\.[^/\s"]+/[^/\s"]+/[^"\s]*)', decoded_string)
            if not kwik_link_match:
                raise RuntimeError("Failed to extract Kwik link from decoded content")
            kwik_link = kwik_link_match.group(1).replace('/d/', '/f/')


        return self.fetch_kwik_dlink(kwik_link)


class Animepahe:
    def __init__(self):
        self.kwik_pahe = KwikPahe()
        self.session = requests.Session()
        self.session.headers.update({
            "accept": "application/json, text/javascript, */*; q=0.0",
            "accept-language": "en-US,en;q=0.9",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0"
        })
        self.session.cookies.set("__ddg2_", "")

    def get_headers(self, link):
        headers = self.session.headers.copy()
        headers["referer"] = link
        return headers

    def fetch_metadata(self, link):
        print("\n\r * Requesting Info..", end="")
        response = self.session.get(link, headers=self.get_headers(link))
        print("\r * Requesting Info : ", end="")
        if response.status_code != 200:
            print("FAILED!")
            raise RuntimeError(f"Failed to fetch {link}, StatusCode: {response.status_code}")
        else:
            print("OK!")

    def fetch_episode(self, link, target_res):
        response = self.session.get(link, headers=self.get_headers(link))
        if response.status_code != 200:
            print(f"\n * Error: Failed to fetch {link}, StatusCode {response.status_code}\n")
            return {}

        episode_data = []
        for match in re.finditer(r'href="(https://pahe\.win/\S*)"[^>]*>([^)]*\))[^<]*<', response.text):
            d_pahe_link, ep_name = match.groups()
            content = {
                "dPaheLink": unquote(d_pahe_link),
                "epName": unquote(ep_name)
            }
            res_match = re.search(r'\b(\d{3,4})p\b', ep_name)
            content["epRes"] = res_match.group(1) if res_match else "0"
            episode_data.append(content)

        if not episode_data:
            raise RuntimeError(f"\n No episodes found in {link}")

        selected_ep_map = None
        if target_res == 0: # Highest
            selected_ep_map = max(episode_data, key=lambda x: int(x['epRes']))
        elif target_res == -1: # Lowest
            selected_ep_map = min(episode_data, key=lambda x: int(x['epRes']))
        else: # Custom
            for episode in episode_data:
                if int(episode['epRes']) == target_res:
                    selected_ep_map = episode
                    break
            if not selected_ep_map:
                selected_ep_map = max(episode_data, key=lambda x: int(x['epRes']))
        
        return selected_ep_map

    def get_series_episode_count(self, link):
        anime_id_match = re.search(r"anime/([a-f0-9-]{36})", link)
        if not anime_id_match:
            raise ValueError("Invalid anime link format")
        anime_id = anime_id_match.group(1)

        api_url = f"https://animepahe.si/api?m=release&id={anime_id}&sort=episode_asc&page=1"
        response = self.session.get(api_url, headers=self.get_headers(link))
        if response.status_code != 200:
            raise RuntimeError(f"Failed to fetch episode count from {api_url}, status code: {response.status_code}")
        
        return response.json().get("total", 0)

    def fetch_series(self, link, ep_count, is_all_episodes, episodes):
        anime_id_match = re.search(r"anime/([a-f0-9-]{36})", link)
        if not anime_id_match:
            raise ValueError("Invalid anime link format")
        anime_id = anime_id_match.group(1)

        links = []
        start_page = 1
        end_page = (ep_count + 29) // 30
        if not is_all_episodes:
            start_page = (episodes[0] + 29) // 30
            end_page = (episodes[1] + 29) // 30

        for page in range(start_page, end_page + 1):
            api_url = f"https://animepahe.si/api?m=release&id={anime_id}&sort=episode_asc&page={page}"
            response = self.session.get(api_url, headers=self.get_headers(link))
            if response.status_code != 200:
                raise RuntimeError(f"Failed to fetch series data from {api_url}, status code: {response.status_code}")
            
            for episode in response.json().get("data", []):
                session = episode.get("session")
                if session:
                    links.append(f"https://animepahe.si/play/{anime_id}/{session}")
        return links

    def extract_link_content(self, link, episodes, target_res, is_series, is_all_episodes):
        episode_list_data = []
        if is_series:
            ep_count = self.get_series_episode_count(link)
            series_ep_links = self.fetch_series(link, ep_count, is_all_episodes, episodes)
            
            start_index = 0
            end_index = len(series_ep_links)
            if not is_all_episodes:
                start_index = episodes[0] - 1
                end_index = episodes[1]

            for i in range(start_index, end_index):
                p_link = series_ep_links[i]
                print(f"\r * Requesting Episode : EP{i+1:02d} ", end="")
                sys.stdout.flush()
                ep_content = self.fetch_episode(p_link, target_res)
                if ep_content:
                    episode_list_data.append(ep_content)
        else:
            ep_content = self.fetch_episode(link, target_res)
            if ep_content:
                episode_list_data.append(ep_content)

        print(f"\r * Requesting Episodes : {len(episode_list_data)} OK!")
        return episode_list_data

    def download_file(self, url, fallback_filename, position, download_dir):
        with self.session.get(url, stream=True) as r:
            r.raise_for_status()
            
            filename = fallback_filename
            content_disposition = r.headers.get('content-disposition')
            if content_disposition:
                filename_match = re.search(r'filename="([^"]+)"', content_disposition)
                if filename_match:
                    filename = unquote(filename_match.group(1))

            filename = "".join(i for i in filename if i not in r'<>:"/|?*')
            filepath = os.path.join(download_dir, filename)

            total_size = int(r.headers.get('content-length', 0))
            chunk_size = 8192

            with tqdm(
                total=total_size,
                unit='B',
                unit_scale=True,
                unit_divisor=1024,
                desc=filename,
                position=position,
                leave=True
            ) as pbar:
                with open(filepath, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=chunk_size):
                        f.write(chunk)
                        pbar.update(len(chunk))

    def extractor(self, is_series, link, target_res, is_all_episodes, episodes, export_filename, export_links, anime_title="Unknown"):
        # Create anime-specific download directory
        safe_title = "".join(i for i in anime_title if i not in r'<>:"/|?*')
        anime_download_dir = os.path.join(DOWNLOAD_DIR, safe_title)
        if not os.path.exists(anime_download_dir):
            os.makedirs(anime_download_dir)
        
        print(f"\n * Anime Title: {anime_title}")
        print(f" * Download Folder: {anime_download_dir}")
        print(" * targetResolution: ", end="")
        if target_res == 0:
            print("Max Available")
        elif target_res == -1:
            print("Lowest Available")
        else:
            print(f"{target_res}p")
        
        print(f" * exportLinks: {export_links}", end="")
        if export_links and export_filename != "links.txt":
            print(f" [{export_filename}]")
        else:
            print()

        if is_series:
            print(" * episodesRange: ", end="")
            if is_all_episodes:
                print("All")
            else:
                print(f"[{episodes[0]}-{episodes[1]}]")

        self.fetch_metadata(link)
        ep_data = self.extract_link_content(link, episodes, target_res, is_series, is_all_episodes)
        
        direct_links = []
        download_tasks = []
        log_ep_num = 1 if is_all_episodes else episodes[0]
        for data in ep_data:
            try:
                print(f"\r * Processing : EP{log_ep_num:02d}", end="")
                d_link = self.kwik_pahe.extract_kwik_link(self.session, data['dPaheLink'])
                direct_links.append((d_link, f"EP{log_ep_num:02d}_{data['epRes']}p.mp4"))
                print(" OK!")
            except Exception as e:
                print(f" FAIL! Reason: {e}")
            log_ep_num += 1

        if export_links:
            with open(export_filename, 'w') as f:
                for link_url, _ in direct_links:
                    f.write(link_url + '\n')
            print(f"\n * Exported : {export_filename}\n")
            return

        # ---- Parallel Downloads ----
        direct_links.sort(key=lambda x: int(re.search(r'EP(\d+)', x[1]).group(1)))
        print(f"\n * Starting parallel downloads to: {anime_download_dir}")
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for pos, (url, filename) in enumerate(direct_links):
                futures.append(executor.submit(self.download_file, url, filename, pos, anime_download_dir))

            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"[ERROR] {e}")


def main():
    anime = input("Enter the name of the anime: ")
    pixels = input("Enter the quality of the video (e.g., 720 or 1080, 0 for best, -1 for worst): ")
    start_ep_input = input("Enter the episode number to start from (hit enter to start from 1): ")
    start_ep = 1 if start_ep_input.strip() == '' else int(start_ep_input)
    end_ep_input = input("Enter the episode number to end at (hit enter to end at the latest): ")
    
    options = Options()
    options.add_argument("start-maximized")
    # options.add_argument("--headless")
    options.add_argument("--disable-gpu")

    try:
        print("Setting up Chrome Driver...")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        print("Driver setup complete.")
    except Exception as e:
        print(f"Fatal Error: Failed to initialize Chrome Driver: {e}")
        exit()

    try:
        print(f"Navigating to Animepahe...")
        driver.get("https://animepahe.si/")
        time.sleep(2)
        print(f"Searching for anime: {anime}")
        try:
            search_box = WebDriverWait(driver, DEFAULT_WAIT_TIME).until(
                EC.presence_of_element_located((By.NAME, "q"))
            )
            search_box.send_keys(anime)
            time.sleep(0.5) # Allow search results to appear
            search_box.send_keys(Keys.RETURN)
            print("Search submitted.")
        except TimeoutException:
            print("Error: Could not find the search bar (By.NAME, 'q').")
            save_debug_info(driver, "search_bar_not_found")
            driver.quit()
            exit()

        print("Looking for search results...")
        try:
            # Wait for the results to load and click the first one
            first_result_link = WebDriverWait(driver, DEFAULT_WAIT_TIME).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".search-results li a"))
            )
            anime_title = first_result_link.text.strip()
            print(f"Found first result: {anime_title}. Clicking...")
            first_result_link.click()
        except TimeoutException:
            print(f"Error: Anime '{anime}' not found or search results structure changed.")
            save_debug_info(driver, "anime_not_found")
            driver.quit()
            exit()
        
        time.sleep(1.5)
        anime_link = driver.current_url
        print(f"Anime page link: {anime_link}")
        driver.quit()

   
        
        is_all_episodes = end_ep_input.strip() == ''
        episodes = []
        if not is_all_episodes:
            episodes = [start_ep, int(end_ep_input)]
        else:
            # For 'all', we still need a start episode for the downloader logic
            episodes = [start_ep, 0]


        animepahe = Animepahe()
        animepahe.extractor(
            is_series=True,
            link=anime_link,
            target_res=int(pixels),
            is_all_episodes=is_all_episodes,
            episodes=episodes,
            export_filename="links.txt",
            export_links=False,
            anime_title=anime_title
        )

    except Exception as e:
        print(f"\n--- A critical error occurred ---")
        print(f"Error: {e}")
        if 'driver' in locals() and driver:
            save_debug_info(driver, "critical_failure")
            driver.quit()


if __name__ == "__main__":
    main()
