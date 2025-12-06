
import requests
import re
import argparse
import sys
from urllib.parse import unquote
import json

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

        api_url = f"https://animepahe.ru/api?m=release&id={anime_id}&sort=episode_asc&page=1"
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
            api_url = f"https://animepahe.ru/api?m=release&id={anime_id}&sort=episode_asc&page={page}"
            response = self.session.get(api_url, headers=self.get_headers(link))
            if response.status_code != 200:
                raise RuntimeError(f"Failed to fetch series data from {api_url}, status code: {response.status_code}")
            
            for episode in response.json().get("data", []):
                session = episode.get("session")
                if session:
                    links.append(f"https://animepahe.ru/play/{anime_id}/{session}")
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

    def download_file(self, url, fallback_filename):
        with self.session.get(url, stream=True) as r:
            r.raise_for_status()
            
            filename = fallback_filename
            content_disposition = r.headers.get('content-disposition')
            if content_disposition:
                filename_match = re.search(r'filename="([^"]+)"', content_disposition)
                if filename_match:
                    filename = unquote(filename_match.group(1))

            filename = "".join(i for i in filename if i not in r'<>:"/|?*')
            
            print(f" * Downloading: {filename}")
            total_size = int(r.headers.get('content-length', 0))
            with open(filename, 'wb') as f:
                downloaded = 0
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        done = int(50 * downloaded / total_size)
                        sys.stdout.write(f"\r[{'=' * done}{' ' * (50-done)}] {downloaded / (1024*1024):.2f}MB / {total_size / (1024*1024):.2f}MB")
                        sys.stdout.flush()
                    else:
                        sys.stdout.write(f"\rDownloaded {downloaded / (1024*1024):.2f}MB")
                        sys.stdout.flush()
        sys.stdout.write('\n')

    def extractor(self, is_series, link, target_res, is_all_episodes, episodes, export_filename, export_links):
        print("\n * targetResolution: ", end="")
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
        log_ep_num = 1 if is_all_episodes else episodes[0]
        for i, data in enumerate(ep_data):
            print(f"\r * Processing : EP{log_ep_num:02d}", end="")
            try:
                d_link = self.kwik_pahe.extract_kwik_link(self.session, data['dPaheLink'])
                direct_links.append(d_link)
                print(" OK!")
                if not export_links:
                    fallback_filename = f"EP{log_ep_num:02d}_{data['epRes']}p.mp4"
                    self.download_file(d_link, fallback_filename)

            except Exception as e:
                print(f" FAIL! Reason: {e}")
            log_ep_num += 1

        if export_links:
            with open(export_filename, 'w') as f:
                for d_link in direct_links:
                    f.write(d_link + '\n')
            print(f"\n * Exported : {export_filename}\n")


def main():
    parser = argparse.ArgumentParser(description="AnimePahe CLI Downloader")
    parser.add_argument("-l", "--link", help="Input anime series link or a single episode link", required=True)
    parser.add_argument("-e", "--episodes", help="Specify episodes to download (all, 1-15)", default="all")
    parser.add_argument("-q", "--quality", help="Set target quality (0 for max, -1 for min)", type=int, default=0)
    parser.add_argument("-x", "--export", help="Export download links to a text file", action="store_true")
    parser.add_argument("-f", "--filename", help="Custom filname for exported file", default="links.txt")
    
    args = parser.parse_args()

    is_series = "anime" in args.link
    
    episodes = []
    is_all_episodes = True
    if args.episodes != "all":
        is_all_episodes = False
        try:
            start, end = map(int, args.episodes.split('-'))
            if start <= 0 or end < start:
                raise ValueError
            episodes = [start, end]
        except ValueError:
            print("Invalid episode range format. Use 'all' or '1-15'.")
            sys.exit(1)

    try:
        animepahe = Animepahe()
        animepahe.extractor(
            is_series,
            args.link,
            args.quality,
            is_all_episodes,
            episodes,
            args.filename,
            args.export
        )
    except Exception as e:
        print(f"\n\n * ERROR: {e} \n\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
