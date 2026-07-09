"""Safety-net tests for the standalone Selenium CLI (repo-root main.py).


These lock the pure link-resolution behavior of the proven CLI so refactors
cannot silently break it. The Selenium/browser driver code is not exercised
here; only the requests-based resolve/selection/range logic is.


Skipped automatically when the CLI's heavy dependencies are not installed.
"""


from __future__ import annotations


import importlib.util
import re
from pathlib import Path


import pytest


# main.py imports these at module load; skip cleanly if unavailable.
pytest.importorskip("requests")
pytest.importorskip("selenium")
pytest.importorskip("tqdm")
pytest.importorskip("webdriver_manager")


ROOT = Path(__file__).resolve().parents[1]
ANIME_ID = "12345678-1234-1234-1234-123456789abc"
ANIME_LINK = f"https://animepahe.org/anime/{ANIME_ID}"




@pytest.fixture(scope="module")
def cli():
   spec = importlib.util.spec_from_file_location("cli_main", ROOT / "main.py")
   module = importlib.util.module_from_spec(spec)
   spec.loader.exec_module(module)
   return module




class FakeResponse:
   def __init__(self, total: int, page: int):
       self.status_code = 200
       self._total = total
       self._page = page
       self.headers = {}
       self.text = ""


   def json(self):
       first = (self._page - 1) * 30 + 1
       last = min(self._total, self._page * 30)
       data = [{"session": f"s{ep}"} for ep in range(first, last + 1)]
       return {"total": self._total, "last_page": (self._total + 29) // 30, "data": data}




class FakeSession:
   """Serves the AnimePahe release API JSON for any page, with a fixed total."""


   def __init__(self, total: int):
       self.total = total
       self.headers: dict[str, str] = {}
       self.requested_pages: list[int] = []


   def get(self, url: str, headers=None, **kwargs):
       match = re.search(r"page=(\d+)", url)
       page = int(match.group(1)) if match else 1
       self.requested_pages.append(page)
       return FakeResponse(self.total, page)




def _make_anime(cli, total: int):
   anime = cli.Animepahe()
   anime.session = FakeSession(total)
   # Echo the play link back so we can assert which episodes were selected,
   # without needing real pahe.win play-page HTML.
   anime.fetch_episode = lambda link, target_res: {
       "dPaheLink": link,
       "epName": link,
       "epRes": "720",
   }
   return anime




def _episode_ids(results: list[dict]) -> list[str]:
   return [item["dPaheLink"].rsplit("/", 1)[-1] for item in results]




# ---- Sacred behavior: must keep passing ----


def test_decode_js_style_roundtrip_exposes_action_and_token(cli):
   kwik = cli.KwikPahe()
   decoded_target = '<form action="/d/example"><input value="tok123"></form>'
   key = "0123456789x"
   encoded = "x".join(str(ord(ch) + 1) for ch in decoded_target)


   result = kwik.decode_js_style(encoded, key, 1, 10)


   assert re.search(r'action="([^"]+)"', result).group(1) == "/d/example"
   assert re.search(r'value="([^"]+)"', result).group(1) == "tok123"




def test_fetch_episode_selects_resolution(cli):
   anime = cli.Animepahe()
   html = (
       '<a href="https://pahe.win/a1" class="x">720p (jpn)</a>'
       '<a href="https://pahe.win/a2" class="x">1080p (jpn)</a>'
   )


   class R:
       status_code = 200
       text = html


   anime.session = FakeSession(1)
   anime.session.get = lambda url, headers=None, **kw: R()


   assert anime.fetch_episode("https://x/play", 0)["epRes"] == "1080"   # highest
   assert anime.fetch_episode("https://x/play", -1)["epRes"] == "720"   # lowest
   assert anime.fetch_episode("https://x/play", 720)["epRes"] == "720"  # exact




# ---- Range math (H1) and start-with-all (B2): correct behavior ----


def test_range_starting_above_page_one_selects_correct_episodes(cli):
   """Range [31, 60] must resolve exactly episodes 31..60 (no IndexError)."""
   anime = _make_anime(cli, total=100)


   results = anime.extract_link_content(
       ANIME_LINK, episodes=[31, 60], target_res=0,
       is_series=True, is_all_episodes=False,
   )


   assert _episode_ids(results) == [f"s{ep}" for ep in range(31, 61)]




def test_all_episodes_with_start_honors_start(cli):
   """'Start at 5, all remaining' must resolve episodes 5..45, not 1..45."""
   anime = _make_anime(cli, total=45)


   results = anime.extract_link_content(
       ANIME_LINK, episodes=[5, 0], target_res=0,
       is_series=True, is_all_episodes=True,
   )


   assert _episode_ids(results) == [f"s{ep}" for ep in range(5, 46)]




def test_default_all_from_one_downloads_everything(cli):
   """Default run (start=1, all) is the proven path and must be unchanged."""
   anime = _make_anime(cli, total=45)


   results = anime.extract_link_content(
       ANIME_LINK, episodes=[1, 0], target_res=0,
       is_series=True, is_all_episodes=True,
   )


   assert _episode_ids(results) == [f"s{ep}" for ep in range(1, 46)]



