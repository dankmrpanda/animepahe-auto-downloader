"""
KwikPahe - Decoder for obfuscated Kwik player links
Ported from main.py with async support and improved error handling
"""

import re
import httpx
import logging
import os
from typing import Optional
import asyncio
from http.cookiejar import LoadError, MozillaCookieJar
from pathlib import Path
from urllib.parse import urljoin, urlparse


logger = logging.getLogger(__name__)

DEFAULT_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/147.0.0.0 Safari/537.36"
)


class KwikDecodeError(Exception):
    """Raised when Kwik link decoding fails"""
    pass


class KwikPahe:
    """Handles extraction and decoding of Kwik video player links"""
    
    def __init__(self):
        self.base_alphabet = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ+/"
        self.timeout = httpx.Timeout(30.0, connect=10.0)
        self.user_agent = (
            os.environ.get("KWIK_USER_AGENT")
            or os.environ.get("ANIMEPAHE_USER_AGENT")
            or DEFAULT_BROWSER_USER_AGENT
        )
        self.cookie_file = os.environ.get("KWIK_COOKIE_FILE")
        self._cookie_clients_loaded: set[int] = set()
        self._cookie_load_summaries: dict[int, dict[str, object]] = {}
    
    def _base_convert(self, input_str: str, from_base: int, to_base: int) -> int:
        """
        Convert a number from one base to another.
        This is the decoded _0xe16c function from the obfuscated JS.
        """
        from_alphabet = self.base_alphabet[:from_base]
        to_alphabet = self.base_alphabet[:to_base]
        
        # Convert from source base to decimal
        decimal_value = 0
        for idx, char in enumerate(reversed(input_str)):
            pos = from_alphabet.find(char)
            if pos != -1:
                decimal_value += pos * (from_base ** idx)
        
        if decimal_value == 0:
            return 0
        
        # Convert from decimal to target base
        result = ""
        while decimal_value > 0:
            result = to_alphabet[decimal_value % to_base] + result
            decimal_value //= to_base
        
        return int(result) if result else 0
    
    def decode_obfuscated_js(self, encoded: str, key: str, offset: int, base: int) -> str:
        """
        Decode the obfuscated JavaScript string from Kwik pages.
        
        Args:
            encoded: The encoded string
            key: The alphabet key used for encoding
            offset: Character offset value
            base: The base for conversion
            
        Returns:
            Decoded string containing the video URL
        """
        decoded = ""
        i = 0
        
        while i < len(encoded):
            segment = ""
            # Collect characters until we hit the delimiter (key[base])
            while i < len(encoded) and encoded[i] != key[base]:
                segment += encoded[i]
                i += 1
            
            # Replace key characters with their index values
            for j in range(len(key)):
                segment = segment.replace(key[j], str(j))
            
            # Convert and apply offset to get ASCII character
            char_code = self._base_convert(segment, base, 10) - offset
            decoded += chr(char_code)
            i += 1
        
        return decoded

    def _absolute_https_url(self, url: str, base_url: str = "") -> str:
        """Normalize relative/protocol-relative URLs to absolute HTTPS URLs."""
        normalized = (url or "").strip()
        if not normalized:
            return normalized

        if normalized.startswith("/"):
            normalized = urljoin(base_url, normalized)
        elif normalized.startswith("//"):
            normalized = "https:" + normalized

        parsed = urlparse(normalized)
        if parsed.scheme == "http":
            normalized = normalized.replace("http://", "https://", 1)

        return normalized

    def _normalize_kwik_url(self, url: str, base_url: str = "") -> str:
        """Normalize kwik links to absolute HTTPS URLs and force /f/ endpoint."""
        normalized = self._absolute_https_url(url, base_url)
        if not normalized:
            return normalized

        if "/d/" in normalized:
            normalized = normalized.replace("/d/", "/f/")
        return normalized

    def _origin_from_url(self, url: str) -> str:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return ""
        return f"{parsed.scheme}://{parsed.netloc}"

    def _browser_headers(
        self,
        referer: Optional[str] = None,
        origin: Optional[str] = None,
        *,
        navigation: bool = True,
    ) -> dict[str, str]:
        headers = {
            "accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,image/apng,*/*;q=0.8"
            ),
            "accept-language": "en-US,en;q=0.9",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "user-agent": self.user_agent,
        }
        if referer:
            headers["referer"] = referer
        if origin:
            headers["origin"] = origin
        if navigation:
            headers["upgrade-insecure-requests"] = "1"
            headers["sec-fetch-dest"] = "document"
            headers["sec-fetch-mode"] = "navigate"
            headers["sec-fetch-site"] = "cross-site" if referer else "none"
            headers["sec-fetch-user"] = "?1"
        return headers

    def _load_cookie_file(self, client: httpx.AsyncClient) -> None:
        """
        Load user-provided Netscape cookies for Kwik.

        This intentionally reads only an explicit cookie export path from
        KWIK_COOKIE_FILE; it does not inspect browser profile databases.
        """
        client_id = id(client)
        if not self.cookie_file or client_id in self._cookie_clients_loaded:
            return

        path = Path(self.cookie_file).expanduser()
        try:
            jar = MozillaCookieJar(str(path))
            jar.load(ignore_discard=True, ignore_expires=True)
            loaded = 0
            names: set[str] = set()
            for cookie in jar:
                domain = (cookie.domain or "").lstrip(".").lower()
                if not domain.startswith("kwik."):
                    continue
                client.cookies.set(
                    cookie.name,
                    cookie.value,
                    domain=cookie.domain,
                    path=cookie.path or "/",
                )
                loaded += 1
                names.add(cookie.name)
            self._cookie_load_summaries[client_id] = {
                "count": loaded,
                "has_cf_clearance": "cf_clearance" in names,
                "has_kwik_session": "kwik_session" in names,
            }
            if loaded:
                logger.info("Loaded %d Kwik cookies from %s", loaded, path)
            else:
                logger.warning("No Kwik cookies found in %s", path)
        except (FileNotFoundError, LoadError, OSError) as exc:
            self._cookie_load_summaries[client_id] = {
                "count": 0,
                "has_cf_clearance": False,
                "has_kwik_session": False,
            }
            logger.warning("Could not load KWIK_COOKIE_FILE=%s: %s", path, exc)
        finally:
            self._cookie_clients_loaded.add(client_id)
    
    async def _fetch_with_retry(
        self, 
        client: httpx.AsyncClient, 
        url: str, 
        method: str = "GET",
        retries: int = 3,
        **kwargs
    ) -> httpx.Response:
        """Fetch URL with exponential backoff retry"""
        last_error: str | None = None
        last_status: int | None = None
        non_retryable_statuses = {401, 403, 404, 410}
        
        for attempt in range(retries):
            try:
                if method == "GET":
                    kwargs.setdefault("follow_redirects", True)
                    response = await client.get(url, **kwargs)
                else:
                    response = await client.post(url, **kwargs)
                
                if 200 <= response.status_code < 400:
                    return response

                last_error = f"HTTP {response.status_code}"
                last_status = response.status_code
                if response.status_code in non_retryable_statuses:
                    break
            except Exception as e:
                last_error = str(e)
            
            # Exponential backoff
            if attempt < retries - 1:
                await asyncio.sleep(2 ** attempt)
        
        if last_status == 403 and urlparse(url).netloc.endswith("kwik.cx"):
            if self.cookie_file:
                summary = self._cookie_load_summaries.get(id(client), {})
                loaded_count = int(summary.get("count") or 0)
                has_cf_clearance = bool(summary.get("has_cf_clearance"))
                has_kwik_session = bool(summary.get("has_kwik_session"))
                if loaded_count:
                    cookie_detail = (
                        f"Loaded {loaded_count} Kwik cookies from KWIK_COOKIE_FILE "
                        f"(cf_clearance={'yes' if has_cf_clearance else 'no'}, "
                        f"kwik_session={'yes' if has_kwik_session else 'no'}), "
                        "but Kwik still returned HTTP 403. This usually means Cloudflare "
                        "rejected the exported browser session. Refresh cookies.txt and "
                        "user-agent.txt from the same browser session, confirm the browser "
                        "can still open the Kwik page on this same IP, then fully restart "
                        "the app."
                    )
                    raise KwikDecodeError(cookie_detail)
                raise KwikDecodeError(
                    "Kwik returned HTTP 403 with KWIK_COOKIE_FILE configured, but no usable "
                    "Kwik cookies were loaded from it. Export fresh kwik.cx cookies in "
                    "Netscape format and restart the app."
                )
            raise KwikDecodeError(
                "Kwik returned HTTP 403 before the page could be decoded. The browser trace "
                "shows Cloudflare challenge traffic, and the CSV export does not include the "
                "cookies needed to reuse that browser session. Export fresh kwik.cx cookies in "
                "Netscape format and start the app with KWIK_COOKIE_FILE set."
            )

        raise KwikDecodeError(f"Failed to fetch {url} after {retries} attempts: {last_error}")
    
    async def fetch_direct_link(
        self, 
        client: httpx.AsyncClient,
        form_action_url: str,
        token: str, 
        session_cookie: str,
        page_url: str,
    ) -> str:
        """
        Submit the token to get the redirect to the direct download link.
        
        Args:
            client: HTTP client
            form_action_url: The form action URL from the Kwik page
            token: The extracted token
            session_cookie: The kwik_session cookie value
            page_url: The Kwik page URL used as the form referer
            
        Returns:
            Direct download URL
        """
        if session_cookie:
            client.cookies.set("kwik_session", session_cookie)

        origin = self._origin_from_url(form_action_url)
        headers = self._browser_headers(
            referer=page_url,
            origin=origin or None,
            navigation=False,
        )
        
        response = await client.post(
            form_action_url,
            headers=headers,
            data={"_token": token},
            follow_redirects=False
        )
        
        if response.status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get("location")
            if location:
                return self._absolute_https_url(location, base_url=form_action_url)
        
        raise KwikDecodeError(f"No redirect found from Kwik POST (status: {response.status_code})")
    
    async def decode_kwik_page(
        self, 
        client: httpx.AsyncClient,
        kwik_url: str,
        retries: int = 5,
        referer: Optional[str] = None,
    ) -> str:
        """
        Fetch and decode a Kwik page to extract the direct download link.
        
        Args:
            client: HTTP client
            kwik_url: URL to the Kwik page (e.g., https://kwik.si/f/...)
            retries: Number of retry attempts
            
        Returns:
            Direct download URL
        """
        if retries <= 0:
            raise KwikDecodeError("Exceeded retry limit for Kwik decode")
        
        try:
            self._load_cookie_file(client)
            response = await self._fetch_with_retry(
                client,
                kwik_url,
                headers=self._browser_headers(referer=referer),
            )
            page_url = str(response.url)
            
            # Clean the response text
            clean_text = response.text.replace("\r\n", "").replace("\r", "").replace("\n", "")
            
            # Extract session cookie
            set_cookie = response.headers.get("set-cookie", "")
            session_match = re.search(r"kwik_session=([^;]*);", set_cookie)
            session_cookie = session_match.group(1) if session_match else ""
            
            # Try to find the encoding parameters
            # Pattern: ("encoded_string", some_number, "alphabet_key", offset, base, another_number)
            encoded_match = re.search(
                r'\(\s*"([^"]+)"\s*,\s*\d+\s*,\s*"([^"]+)"\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*\d+\s*\)',
                clean_text
            )
            
            if not encoded_match:
                # Retry if pattern not found
                await asyncio.sleep(1)
                return await self.decode_kwik_page(client, kwik_url, retries - 1, referer=referer)
            
            encoded_string, alphabet_key, offset, base = encoded_match.groups()
            offset = int(offset)
            base = int(base)
            
            # Decode the obfuscated JS
            decoded = self.decode_obfuscated_js(encoded_string, alphabet_key, offset, base)
            
            # Extract the form action URL and token
            action_match = re.search(r'action="([^"]+)"', decoded)
            token_match = re.search(r'value="([^"]+)"', decoded)
            
            if not action_match or not token_match:
                await asyncio.sleep(1)
                return await self.decode_kwik_page(client, kwik_url, retries - 1, referer=referer)
            
            form_action = self._absolute_https_url(action_match.group(1), base_url=page_url)
            token = token_match.group(1)
            
            # Get the direct link
            direct_link = await self.fetch_direct_link(client, form_action, token, session_cookie, page_url)
            parsed = urlparse(direct_link)
            if retries > 1 and parsed.netloc.startswith("kwik.") and parsed.path.startswith("/f/"):
                # Some responses return an intermediate kwik URL; resolve once more.
                return await self.decode_kwik_page(client, direct_link, retries - 1, referer=page_url)
            return direct_link
            
        except KwikDecodeError:
            raise
        except Exception as e:
            if retries > 1:
                await asyncio.sleep(1)
                return await self.decode_kwik_page(client, kwik_url, retries - 1, referer=referer)
            raise KwikDecodeError(f"Failed to decode Kwik page: {e}")
    
    async def extract_download_link(
        self, 
        client: httpx.AsyncClient,
        pahe_embed_url: str
    ) -> str:
        """
        Extract the direct download link from a pahe.win embed page.
        
        Args:
            client: HTTP client with proper session/cookies
            pahe_embed_url: URL to the pahe.win embed page
            
        Returns:
            Direct download URL to the video file
        """
        if pahe_embed_url.startswith("http://pahe.win/"):
            pahe_embed_url = "https://" + pahe_embed_url[len("http://") :]
        elif pahe_embed_url.startswith("//pahe.win/"):
            pahe_embed_url = "https:" + pahe_embed_url

        response = await self._fetch_with_retry(
            client,
            pahe_embed_url,
            headers=self._browser_headers(referer="https://animepahe.pw/"),
        )
        
        if response.status_code != 200:
            raise KwikDecodeError(f"Failed to fetch embed page: {response.status_code}")
        
        clean_text = response.text.replace("\r\n", "").replace("\r", "").replace("\n", "")
        
        # Try to find direct Kwik link first
        kwik_match = re.search(r'(https?://kwik\.[^/\s"]+/[^/\s"]+/[^"\s]*)', clean_text)
        
        if kwik_match:
            kwik_url = kwik_match.group(1)
        else:
            # Try to decode from obfuscated content
            encoded_match = re.search(
                r'\(\s*"([^",]*)"\s*,\s*\d+\s*,\s*"([^",]*)"\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*\d+[a-zA-Z]?\s*\)',
                clean_text
            )
            
            if not encoded_match:
                raise KwikDecodeError(f"Could not extract Kwik link from {pahe_embed_url}")
            
            encoded_string, alphabet_key, offset, base = encoded_match.groups()
            decoded = self.decode_obfuscated_js(encoded_string, alphabet_key, int(offset), int(base))
            
            kwik_match = re.search(r'(https?://kwik\.[^/\s"]+/[^/\s"]+/[^"\s]*)', decoded)
            if not kwik_match:
                raise KwikDecodeError("Could not find Kwik link in decoded content")
            
            kwik_url = kwik_match.group(1)
        
        kwik_url = self._normalize_kwik_url(kwik_url)
        
        return await self.decode_kwik_page(client, kwik_url, referer=pahe_embed_url)
