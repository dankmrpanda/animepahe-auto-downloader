# Deferred Items (Security Hardening + Transport Alignment)


Last reviewed: 2026-07-08


## Purpose


During the July 2026 bug-fix pass, the items below were identified but
consciously deferred rather than fixed. They are recorded here so they are not
lost.


Context that informed the deferral decisions:


- This application is localhost-only. CORS origins are restricted to
 `http://localhost` and `http://127.0.0.1` on ports 5173 and 8000
 (`web/main.py:104-109`), and Uvicorn binds to `127.0.0.1`
 (`web/main.py:150`). This reduces, but does not eliminate, the practical risk
 of the browser-facing items: a page open in the same browser can still reach a
 localhost server.
- Each item below should be revisited. The localhost-only posture is a
 mitigation, not a fix, and the transport item is a resilience/anti-bot concern
 rather than a browser-security one.


Severity ratings are relative to this localhost-only deployment.


---


## SEC-1 â€” WebSocket endpoint has no Origin check


**Location(s):**


- `web/api/routes.py:863-882` â€” the `websocket_progress` handler for
 `/api/ws/progress`.
- `web/api/routes.py:865` â€” `await websocket.accept()` is called with no
 validation of the `Origin` header.
- `web/main.py:102-113` â€” the CORS middleware that protects HTTP routes.


**Severity:** Medium.


**Description / risk:**


The `CORSMiddleware` configured in `web/main.py` only governs HTTP requests; the
same-origin/CORS browser protections do not apply to WebSocket connections. The
`websocket_progress` handler accepts every connection unconditionally and then
begins streaming live queue and progress data â€” including anime titles and
output filenames â€” via `broadcast_progress` / `broadcast_status`
(`web/api/routes.py:868-878`, `89-100`).


Because there is no `Origin` check, any website open in the user's browser can
open a WebSocket to `ws://localhost:8000/api/ws/progress` (a cross-site
WebSocket hijack) and read what the user is currently searching for and
downloading. This is an information-disclosure vector even in a localhost-only
deployment.


**Why deferred:**


The app is localhost-only and the exposed data is low-sensitivity (queue and
progress metadata rather than credentials), so this was ranked below the
functional bug fixes prioritized in the July 2026 pass.


**Suggested fix:**


Validate the connection origin before accepting it. Read
`websocket.headers['origin']` (or `websocket.headers.get('origin')`), compare it
against the same localhost allow-list used for CORS in `web/main.py:104-109`,
and call `await websocket.close()` for a missing or mismatched origin *before*
(or instead of) `websocket.accept()`. Consider extracting the allow-list into a
shared constant so the HTTP and WebSocket paths cannot drift.


---


## SEC-2 â€” CSRF on no-body, state-changing POST endpoints


**Location(s):** `web/api/routes.py`


- `/api/queue/clear` â€” `web/api/routes.py:569-575`
- `/api/queue/pause` â€” `web/api/routes.py:600-606`
- `/api/queue/resume` â€” `web/api/routes.py:609-615`
- `/api/queue/retry` â€” `web/api/routes.py:501-507`
- `/api/maintenance/cleanup` â€” `web/api/routes.py:811-837`


**Severity:** Medium.


**Description / risk:**


These endpoints change server state and take no request body. CORS prevents a
malicious cross-origin page from *reading* the response, but it does not prevent
the browser from *sending* a "simple" cross-origin POST in the first place. A
malicious page open in the user's browser while the app is running could
therefore fire these POSTs and pause the queue, clear completed tasks, retry
failed tasks, or trigger maintenance cleanup (which pauses and drains active
downloads and removes stale partials/orphan entries â€” see
`web/api/routes.py:818-837`).


The impact is disruption and denial-of-progress rather than data theft, but it
is still an unauthorized state change driven from another origin.


**Why deferred:**


Impact is limited to local, reversible queue disruption on a localhost-only app,
and closing it cleanly touches every state-changing route, so it was deferred
past the functional fixes in the July 2026 pass.


**Suggested fix:**


Require proof that the request came from the app's own frontend on every
state-changing route. Two standard options:


- Require a custom request header (for example `X-Requested-With`) that the
 frontend always sends and that the server enforces. A custom header cannot be
 attached to a cross-origin "simple" request without triggering a CORS
 preflight, which the localhost allow-list will reject.
- Issue and validate a CSRF token.


Enforce the chosen mechanism via a dependency or middleware so it is applied
uniformly to all POST/PUT/DELETE routes rather than per-handler.


---


## XSS â€” Unescaped external fields interpolated into innerHTML


**Location(s):** `frontend/src/main.js`


- `renderSearchResults` â€” `frontend/src/main.js:697-745`. Escaped: `title`.
 Not escaped: `poster` (interpolated into `src="${anime.poster || ''}"` at
 line 709 and into `data-poster` / the MAL upgrade at lines 708, 739-740),
 `session` (`data-session="${anime.session}"`, line 708), `type` (line 714),
 `year` (line 716), and `status` (line 717).
- `renderAnimeInfo` â€” `frontend/src/main.js:777-810`. Escaped: `title`,
 `synopsis`, alt titles. Not escaped: `poster` (`src="${anime.poster || ''}"`,
 line 785), `genres` (line 780), `type` (line 792), `status` (line 793), and
 `aired` / `year` (line 794).
- Existing helper: `escapeHtml` â€” `frontend/src/main.js:1998-2003`.


**Severity:** Medium (Low in the default localhost-only, trusted-upstream case).


**Description / risk:**


Both render functions build markup with template strings assigned to
`innerHTML`. Titles and synopsis are routed through `escapeHtml`, but several
other externally sourced fields are interpolated raw. These values originate
from upstream services (AnimePahe search/detail responses and MAL poster
lookups). A crafted, compromised, or MITM'd upstream response could place markup
in any unescaped field â€” for example a `poster` value that breaks out of the
`src` attribute, or a `genres`/`type`/`status`/`year`/`aired` string containing
a tag â€” and have it execute script in the application's own origin.


**Why deferred:**


Some low-severity frontend fixes are being applied separately. Comprehensive XSS
hardening across *all* interpolated external fields (not just titles/synopsis)
is the part deferred here.


**Suggested fix:**


- Route every interpolated external value through the existing `escapeHtml`
 helper: `session`, `type`, `year`, `status`, `aired`, and each entry of
 `genres` in both functions.
- For images, avoid interpolating the URL into the `src` attribute string. Set
 it via property assignment after the element exists (`img.src = anime.poster`),
 as is already done for the MAL upgrade at `frontend/src/main.js:739`, and
 escape `poster` anywhere it is placed into an attribute (for example the
 `data-poster` attribute at line 708).
- Consider a small helper that builds these nodes with DOM APIs / `textContent`
 instead of `innerHTML` for fully external records.


---


## Transport UA/impersonation alignment (B2-clearance)


**Location(s):**


- `web/core/http_client.py:33` â€” `IMPERSONATE_TARGET` is a fixed value
 (`ANIMEPAHE_CURL_IMPERSONATE` or `"chrome"`) passed to every session in
 `make_async_session` (`web/core/http_client.py:51-63`).
- `web/core/clearance.py:463-467` â€” `chrome_major_from_user_agent`, a helper
 that extracts the Chrome major version from a user-agent string but is
 currently unused.


**Severity:** Low (resilience / anti-bot; not a browser-security issue).


**Description / risk:**


The `curl_cffi` `impersonate` target is fixed and is not aligned to the Chrome
major version of the minted or exported user-agent that the app actually sends.
The clearance flow mints and stores a real browser `user_agent` alongside
`cf_clearance` (`web/core/clearance.py:265-276`), but the transport keeps
impersonating a generic `chrome` target regardless. When the sent UA string and
the TLS / HTTP-2 / client-hint fingerprint produced by `curl_cffi` disagree on
the Chrome version, that mismatch is itself a signal Cloudflare/DDoS-Guard can
use to flag the client as a bot, undermining the impersonation the transport
swap was intended to provide. The existing `chrome_major_from_user_agent`
helper appears intended to close this gap but is not wired in.


**Why deferred:**


Naively setting `chrome{major}` from an arbitrary user-agent can *break* the
transport, because `curl_cffi` only supports a specific set of Chrome
impersonation targets. Picking a version curl_cffi does not support would fail
requests outright. Getting this right requires live validation against
`curl_cffi`'s supported target list and against real Cloudflare responses, which
was out of scope for the July 2026 fix pass.


**Suggested fix:**


When a user-agent is known (minted or exported), map its Chrome major (via
`chrome_major_from_user_agent`) to the nearest `curl_cffi`-supported
`chrome<major>` impersonation target, with a safe fallback to the generic
`chrome` target when no supported match exists. Validate the chosen target
against `curl_cffi`'s supported list at selection time and confirm the result
against live Cloudflare responses before adopting it as the default.




