from __future__ import annotations

import re

from core.kwik import KwikPahe


def test_base_convert_handles_kwik_alphabet() -> None:
    kwik = KwikPahe()

    assert kwik._base_convert("10", 16, 10) == 16
    assert kwik._base_convert("z", 36, 10) == 35


def test_decode_obfuscated_js_exposes_form_action_and_token() -> None:
    kwik = KwikPahe()
    decoded = '<form action="/d/example"><input name="_token" value="tok123"></form>'
    key = "0123456789x"
    encoded = "x".join(str(ord(char) + 1) for char in decoded)

    result = kwik.decode_obfuscated_js(encoded, key=key, offset=1, base=10)

    action = re.search(r'action="([^"]+)"', result)
    token = re.search(r'value="([^"]+)"', result)
    assert action
    assert token
    assert action.group(1) == "/d/example"
    assert token.group(1) == "tok123"
