"""
KwikPahe - Decoder for obfuscated Kwik player links
Ported from main.py with async support and improved error handling
"""

import re
import httpx
from typing import Optional
import asyncio


class KwikDecodeError(Exception):
    """Raised when Kwik link decoding fails"""
    pass


class KwikPahe:
    """Handles extraction and decoding of Kwik video player links"""
    
    def __init__(self):
        self.base_alphabet = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ+/"
        self.timeout = httpx.Timeout(30.0, connect=10.0)
    
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
    
    async def _fetch_with_retry(
        self, 
        client: httpx.AsyncClient, 
        url: str, 
        method: str = "GET",
        retries: int = 3,
        **kwargs
    ) -> httpx.Response:
        """Fetch URL with exponential backoff retry"""
        last_error = None
        
        for attempt in range(retries):
            try:
                if method == "GET":
                    response = await client.get(url, **kwargs)
                else:
                    response = await client.post(url, **kwargs)
                
                if response.status_code == 200 or response.status_code == 302:
                    return response
                    
            except Exception as e:
                last_error = e
            
            # Exponential backoff
            if attempt < retries - 1:
                await asyncio.sleep(2 ** attempt)
        
        raise KwikDecodeError(f"Failed to fetch {url} after {retries} attempts: {last_error}")
    
    async def fetch_direct_link(
        self, 
        client: httpx.AsyncClient,
        kwik_link: str, 
        token: str, 
        session_cookie: str
    ) -> str:
        """
        Submit the token to get the redirect to the direct download link.
        
        Args:
            client: HTTP client
            kwik_link: The Kwik page URL
            token: The extracted token
            session_cookie: The kwik_session cookie value
            
        Returns:
            Direct download URL
        """
        headers = {
            "referer": kwik_link,
            "cookie": f"kwik_session={session_cookie}",
            "origin": kwik_link.rsplit('/', 1)[0],
        }
        
        response = await client.post(
            kwik_link,
            headers=headers,
            data={"_token": token},
            follow_redirects=False
        )
        
        if response.status_code == 302:
            location = response.headers.get("location")
            if location:
                return location
        
        raise KwikDecodeError(f"No redirect found from Kwik POST (status: {response.status_code})")
    
    async def decode_kwik_page(
        self, 
        client: httpx.AsyncClient,
        kwik_url: str,
        retries: int = 5
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
            response = await self._fetch_with_retry(client, kwik_url)
            
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
                return await self.decode_kwik_page(client, kwik_url, retries - 1)
            
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
                return await self.decode_kwik_page(client, kwik_url, retries - 1)
            
            form_action = action_match.group(1)
            token = token_match.group(1)
            
            # Get the direct link
            return await self.fetch_direct_link(client, form_action, token, session_cookie)
            
        except KwikDecodeError:
            raise
        except Exception as e:
            if retries > 1:
                await asyncio.sleep(1)
                return await self.decode_kwik_page(client, kwik_url, retries - 1)
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
        response = await self._fetch_with_retry(client, pahe_embed_url)
        
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
        
        # Ensure we use the /f/ endpoint
        kwik_url = kwik_url.replace('/d/', '/f/')
        
        return await self.decode_kwik_page(client, kwik_url)
