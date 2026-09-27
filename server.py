#!/usr/bin/env python3
"""
Telegram Link Opener v3 — WPSafelink + Deep Chain Resolver

Handles Telegram bot verification links that chain through:
  softurl.in → evloadercarrompool.com (WPSafelink) → final destination

Key insight: WPSafelink embeds the destination in a base64-encoded JSON
blob inside a hidden form field. We extract it directly without needing
to click through ads, wait through countdowns, or pass ad-blocker checks.
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs, urljoin, unquote
from urllib.request import Request, build_opener, HTTPRedirectHandler, HTTPCookieProcessor
import http.cookiejar
import json, re, os, time, html, base64, sys

PORT = int(os.environ.get("PORT", 8787))
HOST = os.environ.get("HOST", "0.0.0.0")
MAX_DEPTH = 25

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)

# Known ad-shortener / gate domains
SHORTENER_KEYWORDS = {
    'softurl', 'adrino', 'adrinolinks', 'shrinkme', 'shrinke',
    'ouo.io', 'ouo.press', 'bit.ly', 'tinyurl', 'cutt.ly',
    'linkvertise', 'link1s', 'shrinkforearn', 'droplink', 'gplinks',
    'earnl', 'clk.sh', 'exe.io', 'fc.lc', 'fas.li', 'mvlinks',
    'mdisk', 'tnlink', 'shareus', 'urlshortx', 'mplaylink',
    'pdiskshortener', 'dulink', 'indianshortner', 'atglinks',
    'ezlinkshortner', 'gyanilinks', 'techymozo', 'bindaaslinks',
    'rocklink', 'nexushort', 'evloadercarrompool', 'wpsafelink',
    'safelink',
}

SKIP_DOMAINS = {
    'google', 'facebook', 'twitter', 'analytics',
    'jquery', 'bootstrap', 'cloudflare', 'googleapis',
    'gstatic', 'doubleclick', 'adsense', 'adserver',
    'fontawesome', 'jsdelivr', 'unpkg', 'googlesyndication',
    'googletagmanager', 'amazon-adsystem', 'pubmatic',
    'adnxs', 'criteo', 'outbrain', 'taboola', 'moatads',
    'wpastra', 'wp-content', 'w3.org',
}


def is_gate_domain(url):
    try:
        domain = urlparse(url).netloc.lower()
        return any(s in domain for s in SHORTENER_KEYWORDS)
    except:
        return False


def is_final_destination(url):
    """True if URL is NOT a gate domain — i.e. it's a real destination."""
    return not is_gate_domain(url) and url.startswith("http")


def is_junk_url(url):
    try:
        domain = urlparse(url).netloc.lower()
        return any(s in domain for s in SKIP_DOMAINS)
    except:
        return False


# ──────────────────── HTTP redirect follower ─────────────────────

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def follow_http_redirects(url, max_hops=15):
    opener = build_opener(NoRedirect())
    current = url
    hops = []
    for _ in range(max_hops):
        req = Request(current, headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        }, method="GET")
        try:
            resp = opener.open(req, timeout=12)
            code, hdrs = resp.status, resp.headers
        except Exception as e:
            if hasattr(e, "code") and hasattr(e, "headers"):
                code, hdrs = e.code, e.headers
            else:
                break
        if code in (301, 302, 303, 307, 308) and hdrs.get("Location"):
            next_url = urljoin(current, hdrs["Location"])
            hops.append({"from": current, "to": next_url, "type": "http-redirect"})
            current = next_url
            continue
        break
    return current, hops


def fetch_page(url, cookie_jar=None):
    """Download a page and return its body as a string."""
    handlers = [NoRedirect()]
    if cookie_jar is not None:
        handlers.append(HTTPCookieProcessor(cookie_jar))
    opener = build_opener(*handlers)
    req = Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Referer": url,
    })
    try:
        resp = opener.open(req, timeout=15)
        return resp.read(2_000_000).decode("utf-8", errors="replace")
    except Exception as e:
        if hasattr(e, "read"):
            return e.read(2_000_000).decode("utf-8", errors="replace")
        return ""


def post_form(action_url, form_data, referer="", cookie_jar=None):
    """Submit a POST form and return the response body or redirect URL."""
    from urllib.parse import urlencode
    data = urlencode(form_data).encode("utf-8")
    handlers = [NoRedirect()]
    if cookie_jar is not None:
        handlers.append(HTTPCookieProcessor(cookie_jar))
    opener = build_opener(*handlers)
    req = Request(action_url, data=data, headers={
        "User-Agent": UA,
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": referer or action_url,
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    }, method="POST")
    try:
        resp = opener.open(req, timeout=15)
        code = resp.status
        hdrs = resp.headers
        if code in (301, 302, 303, 307, 308) and hdrs.get("Location"):
            return fetch_page(urljoin(action_url, hdrs["Location"]), cookie_jar)
        return resp.read(2_000_000).decode("utf-8", errors="replace")
    except Exception as e:
        if hasattr(e, "code") and hasattr(e, "headers"):
            loc = e.headers.get("Location")
            if loc:
                return fetch_page(urljoin(action_url, loc), cookie_jar)
            if hasattr(e, "read"):
                return e.read(2_000_000).decode("utf-8", errors="replace")
        return ""


def post_form_get_redirect(action_url, form_data, referer="", cookie_jar=None):
    """Submit a POST form and return the Location header if redirected."""
    from urllib.parse import urlencode
    data = urlencode(form_data).encode("utf-8")
    handlers = [NoRedirect()]
    if cookie_jar is not None:
        handlers.append(HTTPCookieProcessor(cookie_jar))
    opener = build_opener(*handlers)
    req = Request(action_url, data=data, headers={
        "User-Agent": UA,
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": referer or action_url,
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    }, method="POST")
    try:
        resp = opener.open(req, timeout=15)
        return resp.headers.get("Location"), resp.status
    except Exception as e:
        if hasattr(e, "code") and hasattr(e, "headers"):
            return e.headers.get("Location"), e.code
        return None, 0


# ──────────────────── Softurl.in form handler ─────────────────────

def softurl_resolve(url):
    """
    Handle softurl.in's ad-link form:
    1. GET the page (with cookies)
    2. Extract CSRF token, ad_form_data, and _Token fields
    3. POST the form to get the final redirect
    """
    jar = http.cookiejar.CookieJar()
    body = fetch_page(url, cookie_jar=jar)
    if not body:
        return None

    # Extract form fields
    csrf = re.search(r'name=["\']_csrfToken["\']\s*value=["\']([^"\']+)["\']', body, re.I)
    if not csrf:
        csrf = re.search(r'value=["\']([^"\']+)["\']\s*name=["\']_csrfToken["\']', body, re.I)
    ad_data = re.search(r'name=["\']ad_form_data["\']\s*value=["\']([^"\']+)["\']', body, re.I)
    if not ad_data:
        ad_data = re.search(r'value=["\']([^"\']+)["\']\s*name=["\']ad_form_data["\']', body, re.I)
    token_fields = re.search(r'name=["\']_Token\[fields\]["\']\s*value=["\']([^"\']+)["\']', body, re.I)
    if not token_fields:
        token_fields = re.search(r'value=["\']([^"\']+)["\']\s*name=["\']_Token\[fields\]["\']', body, re.I)
    token_unlocked = re.search(r'name=["\']_Token\[unlocked\]["\']\s*value=["\']([^"\']*)["\']', body, re.I)
    if not token_unlocked:
        token_unlocked = re.search(r'value=["\']([^"\']*)["\']\s*name=["\']_Token\[unlocked\]["\']', body, re.I)

    if not csrf or not ad_data:
        print(f"  [softurl] missing form fields: csrf={bool(csrf)} ad_data={bool(ad_data)}")
        return None

    # Build form data
    form = {
        "_method": "POST",
        "_csrfToken": csrf.group(1),
        "ad_form_data": ad_data.group(1),
    }
    if token_fields:
        form["_Token[fields]"] = unquote(token_fields.group(1))
    if token_unlocked:
        form["_Token[unlocked]"] = unquote(token_unlocked.group(1))

    print(f"  [softurl] POSTing form with CSRF token...")

    # POST to the same URL
    redirect_url, status = post_form_get_redirect(url, form, referer=url, cookie_jar=jar)
    if redirect_url:
        print(f"  [softurl] → redirect to: {redirect_url[:100]}")
        return redirect_url

    # If no redirect header, try getting the body and looking for URLs
    result_body = post_form(url, form, referer=url, cookie_jar=jar)
    if result_body:
        # Look for the destination URL in the response
        urls = re.findall(r'https?://[^\s"\'<>]+', result_body)
        for u in urls:
            if is_final_destination(u):
                print(f"  [softurl] → found in response: {u[:100]}")
                return u

    return None


# ──────────────────── WPSafelink decoder ─────────────────────

def decode_wpsafelink(body, page_url=""):
    """
    Extract the final destination URL from a WPSafelink-protected page.
    WPSafelink stores data as base64 JSON in a hidden form field.
    """
    results = []

    # 1. Find the wpsafelink hidden input
    m = re.search(r'name=["\']newwpsafelink["\']\s+value=["\']([^"\']+)["\']', body, re.I)
    if not m:
        m = re.search(r'value=["\']([^"\']+)["\']\s*/?\s*>\s*</form>', body, re.I)
    if not m:
        return results

    try:
        raw = base64.b64decode(m.group(1)).decode("utf-8", errors="replace")
    except Exception:
        return results

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Maybe there are URLs in the raw decoded string
        urls = re.findall(r'https?://[^\s"\'<>\\]+', raw)
        return [("wpsafe-raw", u) for u in urls if not is_junk_url(u)]

    # The 'linkr' field contains the redirect URL with safelink_redirect param
    linkr = data.get("linkr", "")
    if linkr:
        results.append(("wpsafe-linkr", linkr))
        # Extract safelink_redirect param
        parsed = urlparse(linkr)
        qs = parse_qs(parsed.query)
        sr = qs.get("safelink_redirect", [None])[0]
        if sr:
            try:
                decoded_sr = base64.b64decode(sr).decode("utf-8", errors="replace")
                # This might start with garbage bytes before the JSON
                json_start = decoded_sr.find('{')
                if json_start >= 0:
                    try:
                        sr_data = json.loads(decoded_sr[json_start:])
                        # second_safelink_url is the next hop
                        second = sr_data.get("second_safelink_url", "")
                        if second and second.startswith("http"):
                            results.append(("wpsafe-second", second))
                        # safelink might have the original URL
                        sl = sr_data.get("safelink", "")
                        if sl and sl.startswith("http"):
                            results.append(("wpsafe-safelink", sl))
                    except json.JSONDecodeError:
                        pass
                # Also look for raw URLs
                urls = re.findall(r'https?://[^\s"\'<>\\,}]+', decoded_sr)
                for u in urls:
                    if not is_junk_url(u):
                        results.append(("wpsafe-b64url", u))
            except Exception:
                pass

    # Also check for direct URL fields
    for key in ['newsafelink', 'redirect', 'url', 'link', 'destination']:
        val = data.get(key, "")
        if val and val.startswith("http") and not is_junk_url(val):
            results.append((f"wpsafe-{key}", val))

    # The form action URL is also useful — we need to POST there
    form_action = re.search(r'<form[^>]+id=["\']wpsafelink-landing["\'][^>]+action=["\']([^"\']+)["\']', body, re.I)
    if form_action:
        results.append(("wpsafe-form-action", form_action.group(1)))

    return results


# ──────────────────── HTML/JS scraping ─────────────────────

def scrape_redirects(body, page_url):
    """Extract redirect URLs from HTML/JS content."""
    candidates = []
    current_domain = urlparse(page_url).netloc.lower()

    # Auto-submitting form with base64 value (evloadercarrompool landing page)
    m = re.search(r'<form[^>]+id=["\']landing["\'][^>]+action=["\']([^"\']+)["\']', body, re.I)
    if m:
        form_action = m.group(1)
        go_val = re.search(r'name=["\']go["\']\s+value=["\']([^"\']+)["\']', body, re.I)
        if go_val:
            try:
                decoded = base64.b64decode(go_val.group(1)).decode("utf-8", errors="replace")
                if decoded.startswith("http"):
                    candidates.append(("form-b64", decoded))
            except Exception:
                pass
            # Also POST the form to get the next page
            candidates.append(("form-post", (form_action, {"go": go_val.group(1)})))

    # Meta refresh
    m = re.search(
        r'<meta[^>]+http-equiv\s*=\s*["\']?refresh["\']?[^>]+content\s*=\s*["\']?\d+\s*;\s*url\s*=\s*["\']?([^"\'>\s]+)',
        body, re.I
    )
    if m:
        candidates.append(("meta-refresh", urljoin(page_url, html.unescape(m.group(1)))))

    # JavaScript redirects
    for pat in [
        r'''(?:window\.)?location(?:\.href)?\s*=\s*["']([^"']{10,})["']''',
        r'''location\.replace\(\s*["']([^"']{10,})["']\s*\)''',
    ]:
        for m2 in re.finditer(pat, body, re.I):
            u = html.unescape(m2.group(1))
            if u.startswith("http") and not is_junk_url(u):
                candidates.append(("js-redirect", u))

    # URL in query params of the current page
    qs = parse_qs(urlparse(page_url).query)
    for key in ('r', 'url', 'redirect', 'goto', 'target', 'link', 'dest', 'to', 'next'):
        for val in qs.get(key, []):
            val = unquote(val)
            if val.startswith("http"):
                candidates.append(("url-param", val))

    return candidates


# ──────────────────── Playwright (last resort) ─────────────────────

def playwright_resolve(url, timeout_s=60):
    """Use headless browser for pages that need full JS execution."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [playwright] not installed")
        return url, []

    hops = []
    final = url

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent=UA,
                viewport={"width": 1280, "height": 720},
                ignore_https_errors=True,
            )
            page = ctx.new_page()

            # Block ads/tracking but allow essential scripts
            def route_handler(route):
                req_url = route.request.url
                rtype = route.request.resource_type
                if rtype in ("image", "media", "font"):
                    route.abort()
                elif any(ad in req_url for ad in [
                    'googlesyndication', 'doubleclick', 'google-analytics',
                    'facebook.net', 'pubmatic', 'criteo', 'popads',
                    'amazon-adsystem', 'outbrain', 'taboola',
                ]):
                    route.abort()
                else:
                    route.continue_()
            page.route("**/*", route_handler)

            prev_url = url
            def on_nav(frame):
                nonlocal prev_url, final
                if frame == page.main_frame and frame.url != prev_url and frame.url != "about:blank":
                    print(f"  [playwright] nav: {frame.url[:100]}")
                    hops.append({"from": prev_url, "to": frame.url, "type": "browser-nav"})
                    prev_url = frame.url
                    final = frame.url
            page.on("framenavigated", on_nav)

            print(f"  [playwright] navigating to {url[:80]}")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=25000)
            except Exception as e:
                print(f"  [playwright] goto error (may be ok): {e}")
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass

            print(f"  [playwright] landed on: {page.url[:80]}")

            # Handle WPSafelink forms
            wpsafe_form = page.query_selector("#wpsafelink-landing")
            if wpsafe_form:
                print(f"  [playwright] submitting WPSafelink form")
                page.evaluate("document.getElementById('wpsafelink-landing').submit()")
                time.sleep(3)
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass

            # Main interaction loop
            start = time.time()
            while time.time() - start < timeout_s:
                current_url = page.url

                # If we've landed on a non-gate domain, we're done!
                if is_final_destination(current_url) and current_url != url:
                    time.sleep(1)
                    if page.url == current_url:
                        print(f"  [playwright] reached destination: {current_url[:80]}")
                        break

                # Try submitting softurl.in ad form
                ad_form = page.query_selector("input[name='ad_form_data']")
                if ad_form:
                    # Wait for countdown to finish
                    print(f"  [playwright] found ad_form_data, waiting for countdown...")
                    for wait in range(15):
                        time.sleep(2)
                        # Check if "Get Link" button appeared (not disabled)
                        get_link = page.query_selector("a.get-link:not(.disabled), a#link-view:not(.disabled), a:has-text('Get Link'):not(.disabled)")
                        if get_link:
                            print(f"  [playwright] 'Get Link' button found, clicking...")
                            try:
                                get_link.click()
                                time.sleep(3)
                            except Exception:
                                # Try submitting form directly
                                try:
                                    page.evaluate("document.querySelector('form').submit()")
                                    time.sleep(3)
                                except Exception:
                                    pass
                            break
                        # Also try clicking any visible non-disabled link with "Get Link" text
                        try:
                            page.evaluate("""
                                const btn = document.querySelector('#link-view, .get-link');
                                if (btn) {
                                    btn.classList.remove('disabled');
                                    btn.click();
                                }
                            """)
                        except Exception:
                            pass
                    # After clicking, check if we navigated
                    if page.url != current_url:
                        continue
                    # Try force-submitting the form
                    try:
                        page.evaluate("document.querySelector('form').submit()")
                        time.sleep(3)
                    except Exception:
                        pass
                    if page.url != current_url:
                        continue

                # Generic button clicking
                click_selectors = [
                    'a:has-text("Get Link")', 'a:has-text("Continue")',
                    'a:has-text("Skip")', 'a:has-text("Open")',
                    'a:has-text("Verify")', 'a:has-text("Click here")',
                    'a:has-text("Go to Link")', 'a:has-text("Download")',
                    'button:has-text("Get Link")', 'button:has-text("Continue")',
                    '#link-view', '#btn-open', '#continue', '#skip',
                    'img[alt="DOWNLOAD LINK"]',
                ]
                clicked = False
                for sel in click_selectors:
                    try:
                        el = page.query_selector(sel)
                        if el and el.is_visible():
                            el.click()
                            clicked = True
                            time.sleep(3)
                            break
                    except Exception:
                        pass
                if not clicked:
                    time.sleep(3)

                if time.time() - start > timeout_s * 0.7 and not is_gate_domain(page.url):
                    break

            final = page.url
            browser.close()
    except Exception as e:
        print(f"  [playwright] error: {e}")
        import traceback
        traceback.print_exc()

    return final, hops


# ──────────────────── Master resolver ─────────────────────

def deep_resolve(original_url):
    """
    Multi-strategy deep resolver. Follows the full chain:
    softurl → evloadercarrompool (WPSafelink) → ... → final destination.
    """
    all_hops = []
    visited = set()
    current = original_url
    methods = set()

    for depth in range(MAX_DEPTH):
        if current in visited:
            break
        visited.add(current)
        print(f"  [{depth}] {current[:100]}")

        # ── Step 1: Follow HTTP redirects ──
        after_http, http_hops = follow_http_redirects(current)
        if http_hops:
            all_hops.extend(http_hops)
            methods.add("http-redirect")
            current = after_http
            if current in visited:
                continue
            visited.add(current)
            print(f"  [{depth}] → http redirect → {current[:100]}")

        # ── Step 2: Fetch page and analyze ──
        body = fetch_page(current)
        if not body:
            break

        # ── Step 3: Check for auto-submit landing form (evloadercarrompool pattern) ──
        landing_form = re.search(r'<form[^>]+id=["\']landing["\'][^>]+action=["\']([^"\']+)["\']', body, re.I)
        if landing_form:
            go_val = re.search(r'name=["\']go["\']\s+value=["\']([^"\']+)["\']', body, re.I)
            if go_val:
                form_action = landing_form.group(1)
                print(f"  [{depth}] → found landing form, POSTing to {form_action[:80]}")
                post_body = post_form(form_action, {"go": go_val.group(1)}, referer=current)
                if post_body:
                    # This should give us the article page with WPSafelink
                    all_hops.append({"from": current, "to": form_action, "type": "form-post"})
                    methods.add("form-post")
                    body = post_body
                    current = form_action  # approximate — the real URL may differ

        # ── Step 4: WPSafelink extraction (the main technique!) ──
        wpsafe_results = decode_wpsafelink(body, current)
        if wpsafe_results:
            print(f"  [{depth}] → WPSafelink found! {len(wpsafe_results)} entries")
            methods.add("wpsafelink-decode")

            # Prioritize: linkr > second_safelink_url > form-action
            best_url = None
            for label, val in wpsafe_results:
                if isinstance(val, tuple):
                    continue  # form-post tuples, handled above
                print(f"      {label}: {str(val)[:100]}")
                if label == "wpsafe-linkr" and isinstance(val, str) and val.startswith("http"):
                    # The linkr URL itself can be followed — it's the redirect that
                    # skips the countdown and goes straight to the destination
                    linkr_url = val
                    all_hops.append({"from": current, "to": linkr_url, "type": "wpsafe-linkr"})

                    # Follow the linkr URL (it should redirect to the real destination)
                    linkr_after, linkr_hops = follow_http_redirects(linkr_url)
                    all_hops.extend(linkr_hops)
                    if linkr_after != linkr_url:
                        current = linkr_after
                        best_url = current
                        print(f"  [{depth}] → linkr resolved to {current[:100]}")
                    else:
                        # linkr didn't redirect — try the safelink_redirect param
                        pass

                elif label == "wpsafe-second" and isinstance(val, str):
                    if not best_url:
                        best_url = val
                        all_hops.append({"from": current, "to": val, "type": "wpsafe-second-hop"})

                elif label == "wpsafe-b64url" and isinstance(val, str):
                    if not best_url and not is_gate_domain(val):
                        best_url = val
                        all_hops.append({"from": current, "to": val, "type": "wpsafe-b64"})

            if best_url:
                current = best_url
                # If still on a gate domain, continue the loop
                if is_gate_domain(current):
                    continue
                # Otherwise, do one final HTTP redirect follow
                final_http, final_hops = follow_http_redirects(current)
                if final_hops:
                    all_hops.extend(final_hops)
                    methods.add("http-redirect")
                    current = final_http
                break

        # ── Step 5: Generic HTML/JS scraping ──
        scraped = scrape_redirects(body, current)
        found_next = False
        for label, val in scraped:
            if isinstance(val, tuple):
                # form-post
                action, form_data = val
                print(f"  [{depth}] → posting form to {action[:80]}")
                post_body = post_form(action, form_data, referer=current)
                if post_body:
                    all_hops.append({"from": current, "to": action, "type": "form-post"})
                    methods.add("form-post")
                    body = post_body
                    current = action
                    # Re-check for WPSafelink in the POST result
                    wpsafe2 = decode_wpsafelink(body, current)
                    if wpsafe2:
                        for l2, v2 in wpsafe2:
                            if isinstance(v2, str) and v2.startswith("http") and l2 == "wpsafe-linkr":
                                all_hops.append({"from": current, "to": v2, "type": "wpsafe-linkr"})
                                lr, lr_hops = follow_http_redirects(v2)
                                all_hops.extend(lr_hops)
                                current = lr
                                found_next = True
                                break
                    if found_next:
                        break
            elif isinstance(val, str) and val.startswith("http"):
                if val not in visited and not is_junk_url(val):
                    all_hops.append({"from": current, "to": val, "type": label})
                    methods.add("html-scrape")
                    current = val
                    found_next = True
                    break

        if found_next:
            if not is_gate_domain(current):
                # One final redirect follow
                fr, fh = follow_http_redirects(current)
                if fh:
                    all_hops.extend(fh)
                    current = fr
                break
            continue

        # ── Step 6: Softurl.in form handler (fast, no browser needed) ──
        if 'softurl' in urlparse(current).netloc.lower():
            print(f"  [{depth}] → trying softurl form POST for {current[:80]}")
            soft_result = softurl_resolve(current)
            if soft_result and soft_result != current:
                all_hops.append({"from": current, "to": soft_result, "type": "softurl-form"})
                methods.add("softurl-form")
                current = soft_result
                if is_gate_domain(current):
                    continue
                # Final redirect follow
                fr, fh = follow_http_redirects(current)
                if fh:
                    all_hops.extend(fh)
                    current = fr
                break

        # ── Step 7: Playwright as absolute last resort ──
        if is_gate_domain(current) or current == original_url:
            print(f"  [{depth}] → trying Playwright for {current[:80]}")
            pw_result, pw_hops = playwright_resolve(current)
            if pw_hops:
                all_hops.extend(pw_hops)
                methods.add("browser")
            if pw_result != current:
                current = pw_result
                if is_gate_domain(current):
                    continue
                break

        break

    # ── Safety net: if still on a gate domain, force Playwright ──
    if is_gate_domain(current) and current != original_url:
        print(f"  [safety] still on gate domain, forcing Playwright...")
        pw_result, pw_hops = playwright_resolve(current)
        if pw_hops:
            all_hops.extend(pw_hops)
            methods.add("browser")
        if pw_result != current:
            current = pw_result

    method_str = " + ".join(sorted(methods)) if methods else "direct"
    return current, all_hops, method_str


# ──────────────────────────────── HTTP server ─────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def send_json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def do_GET(self):
        p = urlparse(self.path)
        if p.path == "/":
            try:
                data = open("index.html", "rb").read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except FileNotFoundError:
                self.send_json(404, {"error": "index.html not found"})
            return

        if p.path != "/resolve":
            self.send_json(404, {"error": "Not found"})
            return

        target = parse_qs(p.query).get("url", [None])[0]
        if not target:
            self.send_json(400, {"error": "Missing url"})
            return
        u = urlparse(target)
        if u.scheme not in ("http", "https") or not u.netloc:
            self.send_json(400, {"error": "Only http/https URLs allowed"})
            return

        try:
            print(f"\n{'='*60}")
            print(f"  Resolving: {target}")
            print(f"{'='*60}")
            t0 = time.time()
            final_url, hops, method = deep_resolve(target)
            elapsed = round(time.time() - t0, 1)
            print(f"  ✅ Done in {elapsed}s → {final_url[:80]}")
            print(f"  Method: {method} | Hops: {len(hops)}")
            print(f"{'='*60}\n")

            self.send_json(200, {
                "final_url": final_url,
                "method": method,
                "original_url": target,
                "hops": hops,
                "elapsed": elapsed,
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_json(502, {"error": str(e)})

    def log_message(self, fmt, *args):
        print(f"  [{self.log_date_time_string()}] {fmt % args}")


if __name__ == "__main__":
    print(f"""
╔════════════════════════════════════════════════╗
║   ✈️ Telegram Link Opener v3                  ║
║   http://127.0.0.1:{PORT}                        ║
║                                                ║
║   ✓ WPSafelink decoder (softurl, etc.)         ║
║   ✓ HTTP redirect chains                       ║
║   ✓ JavaScript redirect scraping               ║
║   ✓ Auto form submission                       ║
║   ✓ Headless browser fallback                  ║
╚════════════════════════════════════════════════╝
""")
    HTTPServer((HOST, PORT), Handler).serve_forever()
