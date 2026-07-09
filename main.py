import requests
import re
import argparse
import sys
from urllib.parse import unquote, urljoin


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
# (connect timeout, read timeout) for all HTTP calls so a stalled server cannot
# hang the CLI (or a download worker thread) indefinitely.
REQUEST_TIMEOUT = (10, 30)
DOWNLOAD_TIMEOUT = (10, 60)


if not os.path.exists(SCREENSHOT_DIR):
    os.makedirs(SCREENSHOT_DIR)
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)


def save_debug_info(driver, error_name):
    """Saves screenshot for debugging."""
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    screenshot_path = os.path.join(
        SCREENSHOT_DIR, f"error_{error_name}_{timestamp}.png"
    )
    try:
        driver.save_screenshot(screenshot_path)
        print(f"Screenshot saved to: {screenshot_path}")
    except Exception as e:
        print(f"Could not save debug info: {e}")


# Windows reserved device names that cannot be used as file/dir base names.
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def sanitize_cli_name(name, fallback="download"):
    """Return a filesystem-safe file/dir name.


    Removes characters illegal on Windows (<>:"/\\|?*) and control chars,
    collapses runs of whitespace to a single space, strips trailing dots and
    spaces, falls back to ``fallback`` when the result is empty, and prefixes an
    underscore when the base name (before the extension) is a Windows reserved
    device name (CON, PRN, AUX, NUL, COM1-9, LPT1-9).
    """
    name = "" if name is None else str(name)
    # Drop illegal characters and control characters (ord < 32).
    cleaned = "".join(ch for ch in name if ch not in '<>:"/\\|?*' and ord(ch) >= 32)
    # Collapse any whitespace runs into a single space.
    cleaned = re.sub(r"\s+", " ", cleaned)
    # Strip trailing dots and spaces (invalid/awkward on Windows).
    cleaned = cleaned.strip().rstrip(". ")

    if not cleaned:
        return fallback

    base, ext = os.path.splitext(cleaned)
    if base.upper() in _WINDOWS_RESERVED_NAMES:
        cleaned = "_" + cleaned

    return cleaned


class KwikPahe:
    def __init__(self):
        self.base_alphabet = (
            "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ+/"
        )

    def _0xe16c(self, IS, Iy, ms):
        h = self.base_alphabet[:Iy]
        i = self.base_alphabet[:ms]

        j = 0
        for idx, char in enumerate(reversed(IS)):
            pos = h.find(char)
            if pos != -1:
                j += pos * (Iy**idx)

        if j == 0:
            return 0

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

        response = requests.post(
            kwik_link,
            headers=headers,
            data=data,
            allow_redirects=False,
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get("Location")
            if not location:
                raise RuntimeError(
                    f"Redirect Location header missing in response from {kwik_link}"
                )
            # Absolutize relative Location values against the request URL.
            return urljoin(kwik_link, location)
        else:
            raise RuntimeError(
                f"Redirect Location not found in response from {kwik_link}"
            )

    def fetch_kwik_dlink(self, kwik_link, retries=5):
        if retries <= 0:
            raise RuntimeError("Kwik fetch failed: exceeded retry limit")

        try:
            response = requests.get(kwik_link, timeout=REQUEST_TIMEOUT)
            if response.status_code != 200:
                raise RuntimeError(
                    f"Failed to Get Kwik from {kwik_link}, StatusCode: {response.status_code}"
                )

            clean_text = (
                response.text.replace("\r\n", "").replace("\r", "").replace("\n", "")
            )

            kwik_session_match = re.search(
                r"kwik_session=([^;]*);", response.headers.get("set-cookie", "")
            )
            kwik_session = kwik_session_match.group(1) if kwik_session_match else ""

            encoded_match = re.search(
                r'\("([^"]+)",\d+,"([^"]+)",(\d+),(\d+),\d+\)', clean_text
            )
            if not encoded_match:
                return self.fetch_kwik_dlink(kwik_link, retries - 1)

            encoded_string, alphabet_key, offset, base = encoded_match.groups()
            offset = int(offset)
            base = int(base)

            decoded_string = self.decode_js_style(
                encoded_string, alphabet_key, offset, base
            )

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
        response = session.get(link, timeout=REQUEST_TIMEOUT)
        if response.status_code != 200:
            raise RuntimeError(
                f"Failed to Get Kwik from {link}, StatusCode: {response.status_code}"
            )

        clean_text = (
            response.text.replace("\r\n", "").replace("\r", "").replace("\n", "")
        )

        kwik_link = None
        kwik_link_match = re.search(
            r'(https?://kwik\.[^/\s"]+/[^/\s"]+/[^"\s]*)', clean_text
        )

        if kwik_link_match:
            kwik_link = kwik_link_match.group(1).replace("/d/", "/f/")
        else:
            encoded_match = re.search(
                r'\(\s*"([^",]*)"\s*,\s*\d+\s*,\s*"([^",]*)"\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*\d+[a-zA-Z]?\s*\)',
                clean_text,
            )
            if not encoded_match:
                raise RuntimeError(f"Failed to extract encoding parameters from {link}")

            encoded_string, alphabet_key, offset, base = encoded_match.groups()
            offset = int(offset)
            base = int(base)

            decoded_string = self.decode_js_style(
                encoded_string, alphabet_key, offset, base
            )
            kwik_link_match = re.search(
                r'(https?://kwik\.[^/\s"]+/[^/\s"]+/[^"\s]*)', decoded_string
            )
            if not kwik_link_match:
                raise RuntimeError("Failed to extract Kwik link from decoded content")
            kwik_link = kwik_link_match.group(1).replace("/d/", "/f/")

        return self.fetch_kwik_dlink(kwik_link)


class Animepahe:
    def __init__(self):
        self.kwik_pahe = KwikPahe()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "accept": "application/json, text/javascript, */*; q=0.0",
                "accept-language": "en-US,en;q=0.9",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0",
            }
        )
        self.session.cookies.set("__ddg2_", "")

    def get_headers(self, link):
        headers = self.session.headers.copy()
        headers["referer"] = link
        return headers

    def fetch_metadata(self, link):
        print("\n\r * Requesting Info..", end="")
        response = self.session.get(
            link, headers=self.get_headers(link), timeout=REQUEST_TIMEOUT
        )
        print("\r * Requesting Info : ", end="")
        if response.status_code != 200:
            print("FAILED!")
            raise RuntimeError(
                f"Failed to fetch {link}, StatusCode: {response.status_code}"
            )
        else:
            print("OK!")

    def fetch_episode(self, link, target_res):
        response = self.session.get(
            link, headers=self.get_headers(link), timeout=REQUEST_TIMEOUT
        )
        if response.status_code != 200:
            print(
                f"\n * Error: Failed to fetch {link}, StatusCode {response.status_code}\n"
            )
            return {}

        episode_data = []
        for match in re.finditer(
            r'href="(https://pahe\.win/\S*)"[^>]*>([^)]*\))[^<]*<', response.text
        ):
            d_pahe_link, ep_name = match.groups()
            content = {"dPaheLink": unquote(d_pahe_link), "epName": unquote(ep_name)}
            res_match = re.search(r"\b(\d{3,4})p\b", ep_name)
            content["epRes"] = res_match.group(1) if res_match else "0"
            episode_data.append(content)

        if not episode_data:
            # Skip this episode instead of aborting the whole batch: an empty
            # page (not-yet-released, region-locked, or markup change) should not
            # drop every other successfully-resolved episode.
            print(f"\n * Warning: No download options found in {link} (skipping)")
            return {}

        selected_ep_map = None
        if target_res == 0:  # Highest
            selected_ep_map = max(episode_data, key=lambda x: int(x["epRes"]))
        elif target_res == -1:  # Lowest
            selected_ep_map = min(episode_data, key=lambda x: int(x["epRes"]))
        else:  # Custom
            for episode in episode_data:
                if int(episode["epRes"]) == target_res:
                    selected_ep_map = episode
                    break
            if not selected_ep_map:
                selected_ep_map = max(episode_data, key=lambda x: int(x["epRes"]))

        return selected_ep_map

    def get_series_episode_count(self, link):
        anime_id_match = re.search(r"anime/([a-f0-9-]{36})", link)
        if not anime_id_match:
            raise ValueError("Invalid anime link format")
        anime_id = anime_id_match.group(1)

        api_url = (
            f"https://animepahe.org/api?m=release&id={anime_id}&sort=episode_asc&page=1"
        )
        response = self.session.get(
            api_url, headers=self.get_headers(link), timeout=REQUEST_TIMEOUT
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"Failed to fetch episode count from {api_url}, status code: {response.status_code}"
            )

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
            # Always fetch from page 1 so the returned list can be indexed by
            # absolute episode number in extract_link_content. Previously this
            # pruned earlier pages, which made ranges starting past episode 30
            # raise IndexError or select the wrong episodes.
            end_page = (episodes[1] + 29) // 30

        for page in range(start_page, end_page + 1):
            api_url = f"https://animepahe.org/api?m=release&id={anime_id}&sort=episode_asc&page={page}"
            response = self.session.get(
                api_url, headers=self.get_headers(link), timeout=REQUEST_TIMEOUT
            )
            if response.status_code != 200:
                raise RuntimeError(
                    f"Failed to fetch series data from {api_url}, status code: {response.status_code}"
                )

            for episode in response.json().get("data", []):
                session = episode.get("session")
                if session:
                    links.append(f"https://animepahe.org/play/{anime_id}/{session}")
        return links

    def extract_link_content(
        self, link, episodes, target_res, is_series, is_all_episodes
    ):
        episode_list_data = []
        if is_series:
            ep_count = self.get_series_episode_count(link)
            series_ep_links = self.fetch_series(
                link, ep_count, is_all_episodes, episodes
            )

            # Series links are fetched from page 1, so absolute episode numbers
            # map directly onto list indices. Honor the requested start episode
            # for both "all remaining" and explicit-range downloads, and clamp
            # the end so a range beyond the last episode cannot overrun the list.
            start_index = max(0, episodes[0] - 1)
            if is_all_episodes:
                end_index = len(series_ep_links)
            else:
                end_index = min(episodes[1], len(series_ep_links))

            for i in range(start_index, end_index):
                p_link = series_ep_links[i]
                print(f"\r * Requesting Episode : EP{i+1:02d} ", end="")
                sys.stdout.flush()
                ep_content = self.fetch_episode(p_link, target_res)
                if ep_content:
                    # Carry the true episode number so a skipped (empty) episode
                    # does not shift the EPxx labels of the episodes after it.
                    ep_content["epNum"] = i + 1
                    episode_list_data.append(ep_content)
        else:
            ep_content = self.fetch_episode(link, target_res)
            if ep_content:
                ep_content["epNum"] = episodes[0] if episodes else 1
                episode_list_data.append(ep_content)

        print(f"\r * Requesting Episodes : {len(episode_list_data)} OK!")
        return episode_list_data

    def download_file(self, url, fallback_filename, position, download_dir):
        # Use a per-download session: a single requests.Session is not safe for
        # concurrent use across the ThreadPoolExecutor workers. Each download
        # gets its own session that still carries the shared headers/cookies
        # (user-agent, __ddg2_) needed for CDN access.
        session = requests.Session()
        session.headers.update(self.session.headers)
        session.cookies.update(self.session.cookies)
        with session.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT) as r:
            r.raise_for_status()

            filename = fallback_filename
            content_disposition = r.headers.get("content-disposition")
            if content_disposition:
                filename_match = re.search(r'filename="([^"]+)"', content_disposition)
                if filename_match:
                    filename = unquote(filename_match.group(1))

            filename = sanitize_cli_name(filename, fallback=fallback_filename)
            filepath = os.path.join(download_dir, filename)

            total_size = int(r.headers.get("content-length", 0))
            chunk_size = 8192

            with tqdm(
                total=total_size,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                desc=filename,
                position=position,
                leave=True,
            ) as pbar:
                with open(filepath, "wb") as f:
                    for chunk in r.iter_content(chunk_size=chunk_size):
                        f.write(chunk)
                        pbar.update(len(chunk))

    def extractor(
        self,
        is_series,
        link,
        target_res,
        is_all_episodes,
        episodes,
        export_filename,
        export_links,
        anime_title="Unknown",
    ):
        # Create anime-specific download directory
        safe_title = sanitize_cli_name(anime_title, fallback="Unknown")
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
        ep_data = self.extract_link_content(
            link, episodes, target_res, is_series, is_all_episodes
        )

        direct_links = []
        download_tasks = []
        for idx, data in enumerate(ep_data):
            # Use the true episode number carried by extract_link_content so a
            # skipped episode does not misname the files that follow it.
            ep_num = data.get("epNum", episodes[0] + idx)
            try:
                print(f"\r * Processing : EP{ep_num:02d}", end="")
                d_link = self.kwik_pahe.extract_kwik_link(
                    self.session, data["dPaheLink"]
                )
                direct_links.append((d_link, f"EP{ep_num:02d}_{data['epRes']}p.mp4"))
                print(" OK!")
            except Exception as e:
                print(f" FAIL! Reason: {e}")

        if export_links:
            with open(export_filename, "w") as f:
                for link_url, _ in direct_links:
                    f.write(link_url + "\n")
            print(f"\n * Exported : {export_filename}\n")
            return

        # ---- Parallel Downloads ----
        direct_links.sort(key=lambda x: int(re.search(r"EP(\d+)", x[1]).group(1)))
        print(f"\n * Starting parallel downloads to: {anime_download_dir}")
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for pos, (url, filename) in enumerate(direct_links):
                futures.append(
                    executor.submit(
                        self.download_file, url, filename, pos, anime_download_dir
                    )
                )

            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"[ERROR] {e}")


def main():
    anime = input("Enter the name of the anime: ")
    pixels = input(
        "Enter the quality of the video (e.g., 720 or 1080, 0 for best, -1 for worst): "
    )
    start_ep_input = input(
        "Enter the episode number to start from (hit enter to start from 1): "
    )
    end_ep_input = input(
        "Enter the episode number to end at (hit enter to end at the latest): "
    )

    # Validate all numeric inputs up front so bad input yields a friendly
    # message and a clean exit instead of a raw traceback.
    try:
        target_res = int(pixels.strip())
    except ValueError:
        print(
            "Invalid quality: please enter a whole number (e.g., 720 or 1080, 0 for best, -1 for worst)."
        )
        sys.exit(1)

    if start_ep_input.strip() == "":
        start_ep = 1
    else:
        try:
            start_ep = int(start_ep_input.strip())
        except ValueError:
            print(
                "Invalid start episode: please enter a whole number, or hit enter to start from 1."
            )
            sys.exit(1)
        if start_ep < 1:
            print("Invalid start episode: must be 1 or greater.")
            sys.exit(1)

    is_all_episodes = end_ep_input.strip() == ""
    end_ep = 0
    if not is_all_episodes:
        try:
            end_ep = int(end_ep_input.strip())
        except ValueError:
            print(
                "Invalid end episode: please enter a whole number, or hit enter to end at the latest."
            )
            sys.exit(1)
        if end_ep < start_ep:
            print(
                f"Invalid range: end episode ({end_ep}) must be greater than or equal to start episode ({start_ep})."
            )
            sys.exit(1)

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
        sys.exit(1)

    try:
        print(f"Navigating to Animepahe...")
        driver.get("https://animepahe.org/")
        time.sleep(2)
        print(f"Searching for anime: {anime}")
        try:
            search_box = WebDriverWait(driver, DEFAULT_WAIT_TIME).until(
                EC.presence_of_element_located((By.NAME, "q"))
            )
            search_box.send_keys(anime)
            time.sleep(0.5)  # Allow search results to appear
            search_box.send_keys(Keys.RETURN)
            print("Search submitted.")
        except TimeoutException:
            print("Error: Could not find the search bar (By.NAME, 'q').")
            save_debug_info(driver, "search_bar_not_found")
            driver.quit()
            sys.exit(1)

        print("Looking for search results...")
        try:
            # Wait for the results to load and click the first one
            first_result_link = WebDriverWait(driver, DEFAULT_WAIT_TIME).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".search-results li a"))
            )
            # Extract only the first line (anime title), ignoring metadata lines
            anime_title = first_result_link.text.strip().split("\n")[0].strip()
            print(f"Found first result: {anime_title}. Clicking...")
            first_result_link.click()
        except TimeoutException:
            print(
                f"Error: Anime '{anime}' not found or search results structure changed."
            )
            save_debug_info(driver, "anime_not_found")
            driver.quit()
            sys.exit(1)

        time.sleep(1.5)
        anime_link = driver.current_url
        print(f"Anime page link: {anime_link}")
        driver.quit()
        # The browser session is done; clear the reference so the outer
        # `except Exception` handler does not try to screenshot / quit an
        # already-closed driver.
        driver = None

        episodes = []
        if not is_all_episodes:
            episodes = [start_ep, end_ep]
        else:
            # For 'all', we still need a start episode for the downloader logic
            episodes = [start_ep, 0]

        animepahe = Animepahe()
        animepahe.extractor(
            is_series=True,
            link=anime_link,
            target_res=target_res,
            is_all_episodes=is_all_episodes,
            episodes=episodes,
            export_filename="links.txt",
            export_links=False,
            anime_title=anime_title,
        )

    except Exception as e:
        print(f"\n--- A critical error occurred ---")
        print(f"Error: {e}")
        if "driver" in locals() and driver:
            save_debug_info(driver, "critical_failure")
            driver.quit()


if __name__ == "__main__":
    main()
