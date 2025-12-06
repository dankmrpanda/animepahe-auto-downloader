"""
AnimePahe API Client
Handles all interactions with the AnimePahe website
"""

import re
import asyncio
import httpx
import html
from urllib.parse import quote, unquote
from typing import Optional
from dataclasses import dataclass

from core.kwik import KwikPahe, KwikDecodeError


@dataclass
class AnimeSearchResult:
    """Represents a search result from AnimePahe"""
    session: str
    title: str
    type: str  # TV, Movie, OVA, etc.
    episodes: int
    status: str  # Ongoing, Completed
    season: str
    year: int
    score: float
    poster: str


@dataclass
class Episode:
    """Represents an episode from AnimePahe"""
    id: int
    episode: float  # Can be 1.5 for specials
    episode_display: str
    title: str
    snapshot: str
    duration: str
    session: str
    filler: bool
    created_at: str


@dataclass
class DownloadOption:
    """Represents a download option for an episode"""
    pahe_link: str
    quality: str
    resolution: int
    audio: str
    size: str


class AnimePaheError(Exception):
    """Base exception for AnimePahe errors"""
    pass


class AnimePaheClient:
    """Async client for AnimePahe website"""
    
    BASE_URL = "https://animepahe.si"
    
    def __init__(self):
        self.kwik = KwikPahe()
        self.timeout = httpx.Timeout(30.0, connect=10.0)
        self._session_cookie = None
    
    def _get_headers(self, referer: Optional[str] = None) -> dict:
        """Get headers for requests"""
        headers = {
            "accept": "application/json, text/javascript, */*; q=0.01",
            "accept-language": "en-US,en;q=0.9",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "x-requested-with": "XMLHttpRequest",
        }
        if referer:
            headers["referer"] = referer
        return headers
    
    async def _ensure_session(self, client: httpx.AsyncClient) -> None:
        """Ensure we have valid session cookies by visiting the homepage"""
        if self._session_cookie:
            return
            
        response = await client.get(
            self.BASE_URL,
            headers=self._get_headers(),
            follow_redirects=True
        )
        
        # Store any cookies from the response
        if "__ddg2_" not in client.cookies:
            client.cookies.set("__ddg2_", "")
    
    async def _get_mal_details(self, title: str) -> dict:
        """
        Fetch full anime details from MyAnimeList (via Jikan API).
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Jikan API search
                url = f"https://api.jikan.moe/v4/anime?q={quote(title)}&limit=1"
                response = await client.get(url)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("data") and len(data["data"]) > 0:
                        anime = data["data"][0]
                        images = anime.get("images", {}).get("jpg", {})
                        
                        return {
                            "poster": images.get("large_image_url") or images.get("image_url") or "",
                            "synopsis": anime.get("synopsis", ""),
                            "score": anime.get("score", 0.0),
                            "status": anime.get("status", ""),
                            "aired": anime.get("aired", {}).get("string", ""),
                            "genres": [g.get("name") for g in anime.get("genres", [])],
                            "english_title": anime.get("title_english", ""),
                            "japanese_title": anime.get("title_japanese", ""),
                        }
        except Exception as e:
            print(f"MAL fetch failed for {title}: {e}")
        return {}

    async def _get_mal_poster(self, title: str) -> str:
        """
        Fetch anime poster from MyAnimeList (via Jikan API) as a fallback.
        """
        details = await self._get_mal_details(title)
        return details.get("poster", "")

    async def search(self, query: str) -> list[AnimeSearchResult]:
        """
        Search for anime on AnimePahe.
        
        Args:
            query: Search term
            
        Returns:
            List of matching anime results
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            await self._ensure_session(client)
            
            search_url = f"{self.BASE_URL}/api?m=search&l=8&q={quote(query)}"
            
            try:
                response = await client.get(
                    search_url,
                    headers=self._get_headers(f"{self.BASE_URL}/"),
                    follow_redirects=True
                )
                
                if response.status_code != 200:
                    print(f"Search failed: {response.status_code}")
                    return []
                
                # Handle empty or invalid responses
                text = response.text.strip()
                if not text or text == "false" or text == "null":
                    return []
                
                data = response.json()
                
                # data might be False, null, or not have "data" key when no results
                if not data or not isinstance(data, dict):
                    return []
                
                results = []
                
                # Process results
                for item in data.get("data", []) or []:
                    if not isinstance(item, dict):
                        continue
                        
                    # Handle poster URL - ensure it's absolute if relative
                    poster = item.get("poster", "")
                    if poster and not poster.startswith("http"):
                        poster = f"{self.BASE_URL}{poster}" if poster.startswith("/") else poster
                    
                    # If poster is missing or looks invalid (e.g. just base url), try MAL
                    # Note: We don't want to spam MAL for every result if we can avoid it
                    # But if the user says images are broken, we might need to.
                    # For now, let's only fetch if poster is empty or None
                    if not poster:
                        # We can't await here easily without slowing down the loop
                        # But since we need the image, we might have to.
                        # Let's mark it for background fetch or just fetch it.
                        pass 

                    results.append(AnimeSearchResult(
                        session=item.get("session", ""),
                        title=item.get("title", "Unknown"),
                        type=item.get("type", "TV"),
                        episodes=item.get("episodes", 0),
                        status=item.get("status", "Unknown"),
                        season=item.get("season", "Unknown"),
                        year=item.get("year", 0),
                        score=float(item.get("score", 0.0) or 0.0),
                        poster=poster,
                    ))
                
                # If we have results but no posters, try to fetch from MAL in parallel
                # Only do this for the top 3 results to avoid rate limits
                tasks = []
                for i, res in enumerate(results[:5]):
                    if not res.poster or "animepahe" in res.poster: # Assuming animepahe posters might be broken
                        tasks.append(self._update_poster_from_mal(res))
                
                if tasks:
                    await asyncio.gather(*tasks)
                
                return results
            except Exception as e:
                print(f"Search error: {e}")
                return []

    async def _update_poster_from_mal(self, result: AnimeSearchResult):
        """Helper to update poster in place"""
        new_poster = await self._get_mal_poster(result.title)
        if new_poster:
            result.poster = new_poster
    
    async def get_anime_details(self, session_id: str) -> dict:
        """
        Get details for a specific anime.
        
        Args:
            session_id: The anime's session ID
            
        Returns:
            Dictionary with anime details
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            await self._ensure_session(client)
            
            url = f"{self.BASE_URL}/anime/{session_id}"
            response = await client.get(
                url,
                headers=self._get_headers(self.BASE_URL),
                follow_redirects=True
            )
            
            if response.status_code != 200:
                raise AnimePaheError(f"Failed to get anime details: {response.status_code}")
            
            # Extract title from page to use for MAL search
            title_match = re.search(r'<h1[^>]*>(.*?)</h1>', response.text, re.DOTALL)
            if title_match:
                # Remove any HTML tags from the title
                title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
                # Decode HTML entities
                title = html.unescape(title)
            else:
                title = ""

            # Extract poster from og:image as fallback
            poster_match = re.search(r'<meta property="og:image" content="([^"]+)"', response.text)
            pahe_poster = poster_match.group(1) if poster_match else ""
            
            # Extract episode count from the page or use API
            api_url = f"{self.BASE_URL}/api?m=release&id={session_id}&sort=episode_asc&page=1"
            api_response = await client.get(
                api_url,
                headers=self._get_headers(url),
                follow_redirects=True
            )
            
            if api_response.status_code != 200:
                raise AnimePaheError(f"Failed to get episode count: {api_response.status_code}")
            
            api_data = api_response.json()
            
            # Fetch extra details from MAL
            mal_details = {}
            if title:
                mal_details = await self._get_mal_details(title)
            
            # Use MAL poster if available, otherwise use Pahe poster
            final_poster = mal_details.get("poster") or pahe_poster

            return {
                "session": session_id,
                "title": title,
                "total_episodes": api_data.get("total", 0),
                "last_page": api_data.get("last_page", 1),
                "per_page": api_data.get("per_page", 30),
                **mal_details,
                "poster": final_poster
            }
    
    async def get_episodes(
        self, 
        session_id: str, 
        page: int = 1
    ) -> tuple[list[Episode], int]:
        """
        Get episodes for an anime.
        
        Args:
            session_id: The anime's session ID
            page: Page number (30 episodes per page)
            
        Returns:
            Tuple of (list of episodes, total pages)
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            await self._ensure_session(client)
            
            api_url = f"{self.BASE_URL}/api?m=release&id={session_id}&sort=episode_asc&page={page}"
            
            response = await client.get(
                api_url,
                headers=self._get_headers(f"{self.BASE_URL}/anime/{session_id}"),
                follow_redirects=True
            )
            
            if response.status_code != 200:
                raise AnimePaheError(f"Failed to get episodes: {response.status_code}")
            
            data = response.json()
            episodes = []
            
            for item in data.get("data", []):
                episodes.append(Episode(
                    id=item.get("id", 0),
                    episode=item.get("episode", 0),
                    episode_display=str(item.get("episode", 0)),
                    title=item.get("title", ""),
                    snapshot=item.get("snapshot", ""),
                    duration=item.get("duration", ""),
                    session=item.get("session", ""),
                    filler=item.get("filler", 0) == 1,
                    created_at=item.get("created_at", ""),
                ))
            
            return episodes, data.get("last_page", 1)
    
    async def get_all_episodes(self, session_id: str) -> list[Episode]:
        """
        Get all episodes for an anime using parallel fetching.
        
        Args:
            session_id: The anime's session ID
            
        Returns:
            List of all episodes
        """
        # First, get the total page count
        _, total_pages = await self.get_episodes(session_id, 1)
        
        if total_pages == 1:
            episodes, _ = await self.get_episodes(session_id, 1)
            return episodes
        
        # Fetch all pages in parallel
        async def fetch_page(page: int) -> list[Episode]:
            eps, _ = await self.get_episodes(session_id, page)
            return eps
        
        tasks = [fetch_page(p) for p in range(1, total_pages + 1)]
        results = await asyncio.gather(*tasks)
        
        # Flatten and sort by episode number
        all_episodes = [ep for page_eps in results for ep in page_eps]
        all_episodes.sort(key=lambda x: x.episode)
        
        return all_episodes
    
    async def get_episode_download_options(
        self, 
        anime_session: str, 
        episode_session: str
    ) -> list[DownloadOption]:
        """
        Get available download options for an episode.
        
        Args:
            anime_session: The anime's session ID
            episode_session: The episode's session ID
            
        Returns:
            List of download options with different qualities
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            await self._ensure_session(client)
            
            play_url = f"{self.BASE_URL}/play/{anime_session}/{episode_session}"
            
            response = await client.get(
                play_url,
                headers=self._get_headers(f"{self.BASE_URL}/anime/{anime_session}"),
                follow_redirects=True
            )
            
            if response.status_code != 200:
                raise AnimePaheError(f"Failed to get episode page: {response.status_code}")
            
            options = []
            
            # Parse download options from the page
            # Pattern: href="https://pahe.win/..." or similar followed by quality info
            # We look for links that look like download/play links
            for match in re.finditer(
                r'href="([^"]+)"[^>]*>([^<]+)<',
                response.text
            ):
                link, info = match.groups()
                
                # Filter for likely download links (pahe.win, kwik.cx, etc.)
                if not any(d in link for d in ["pahe.win", "kwik.cx", "kwik.si"]):
                    continue

                # Extract resolution from info (e.g., "720p" or "1080p")
                res_match = re.search(r'(\d{3,4})p', info)
                resolution = int(res_match.group(1)) if res_match else 0
                
                # Extract audio info (e.g., "jpn" or "eng")
                audio_match = re.search(r'(jpn|eng|multi)', info.lower())
                audio = audio_match.group(1) if audio_match else "jpn"
                
                # Extract size if available
                size_match = re.search(r'(\d+(?:\.\d+)?\s*(?:MB|GB))', info)
                size = size_match.group(1) if size_match else ""
                
                options.append(DownloadOption(
                    pahe_link=unquote(link),
                    quality=info.strip(),
                    resolution=resolution,
                    audio=audio,
                    size=size,
                ))
            
            # Sort by resolution (highest first)
            options.sort(key=lambda x: x.resolution, reverse=True)
            
            return options
    
    async def get_direct_download_link(
        self, 
        pahe_link: str
    ) -> str:
        """
        Extract the direct download link from a pahe.win embed.
        
        Args:
            pahe_link: The pahe.win embed URL
            
        Returns:
            Direct download URL
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            await self._ensure_session(client)
            client.cookies.set("__ddg2_", "")
            
            return await self.kwik.extract_download_link(client, pahe_link)
    
    async def get_episode_links_batch(
        self,
        anime_session: str,
        episodes: list[Episode],
        target_resolution: int = 0  # 0 = highest, -1 = lowest
    ) -> list[dict]:
        """
        Get download links for multiple episodes.
        
        Args:
            anime_session: The anime's session ID
            episodes: List of episodes to get links for
            target_resolution: Target resolution (0=highest, -1=lowest, or specific like 720)
            
        Returns:
            List of dicts with episode info and download links
        """
        results = []
        
        async def process_episode(episode: Episode) -> dict:
            try:
                options = await self.get_episode_download_options(
                    anime_session, 
                    episode.session
                )
                
                if not options:
                    return {
                        "episode": episode.episode,
                        "session": episode.session,
                        "error": "No download options found"
                    }
                
                # Select option based on target resolution
                selected = None
                if target_resolution == 0:
                    selected = max(options, key=lambda x: x.resolution)
                elif target_resolution == -1:
                    selected = min(options, key=lambda x: x.resolution)
                else:
                    # Find exact match or closest
                    for opt in options:
                        if opt.resolution == target_resolution:
                            selected = opt
                            break
                    if not selected:
                        selected = max(options, key=lambda x: x.resolution)
                
                # Get direct download link
                direct_link = await self.get_direct_download_link(selected.pahe_link)
                
                return {
                    "episode": episode.episode,
                    "session": episode.session,
                    "title": episode.title,
                    "quality": selected.quality,
                    "resolution": selected.resolution,
                    "direct_link": direct_link,
                    "error": None
                }
                
            except Exception as e:
                return {
                    "episode": episode.episode,
                    "session": episode.session,
                    "error": str(e)
                }
        
        # Process episodes with limited concurrency to avoid rate limiting
        semaphore = asyncio.Semaphore(5)
        
        async def limited_process(ep: Episode) -> dict:
            async with semaphore:
                return await process_episode(ep)
        
        tasks = [limited_process(ep) for ep in episodes]
        results = await asyncio.gather(*tasks)
        
        return results
