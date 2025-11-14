#!/usr/bin/env python3
"""
grab_sources_from_site.py

Usage:
    python grab_sources_from_site.py https://example.com output_dir

What it does:
- Fetches the page at the given URL
- Finds <script src="..."> entries and inline scripts
- For each JS, finds a sourceMappingURL comment (or inline data: map)
- Downloads/decodes the .map and reconstructs sources to output_dir
"""

import sys
import os
import re
import json
import base64
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

if len(sys.argv) < 3:
    print("Usage: python grab_sources_from_site.py <page-url> <output-dir>")
    sys.exit(1)

page_url = sys.argv[1].rstrip('/')
out_dir = sys.argv[2]

os.makedirs(out_dir, exist_ok=True)

session = requests.Session()
session.headers.update({"User-Agent": "source-grabber/1.0"})

def get_text(url):
    r = session.get(url, timeout=20)
    r.raise_for_status()
    return r.text, r.url

def save_file(path, content):
    full = os.path.join(out_dir, path)
    d = os.path.dirname(full)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)
    with open(full, "wb") as f:
        if isinstance(content, str):
            content = content.encode("utf-8")
        f.write(content)

def find_scripts_from_html(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    scripts = []
    for s in soup.find_all("script"):
        src = s.get("src")
        if src:
            scripts.append(urljoin(base_url, src))
        else:
            # inline script: keep the content and treat as an entry
            scripts.append({"inline": True, "content": s.string or ""})
    return scripts

# regex for sourceMappingURL
sm_re = re.compile(r'//# sourceMappingURL=(?P<url>.+)$|/\*# sourceMappingURL=(?P<url2>.+)\s*\*/', re.MULTILINE)

def extract_mapping_reference(js_text):
    m = sm_re.search(js_text)
    if not m:
        return None
    url = m.group("url") or m.group("url2")
    return url.strip()

def handle_map_url(map_url_or_data, js_base_url):
    # map_url_or_data might be "data:application/json;base64,..." or a relative/absolute URL
    if map_url_or_data.startswith("data:"):
        # data URL
        try:
            header, b64 = map_url_or_data.split(",", 1)
        except ValueError:
            return None
        # if base64 encoded
        if "base64" in header:
            raw = base64.b64decode(b64)
            return json.loads(raw)
        else:
            return json.loads(b64)
    else:
        # relative/absolute URL
        full_map_url = urljoin(js_base_url, map_url_or_data)
        try:
            r = session.get(full_map_url, timeout=20)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"Failed to fetch/parse map at {full_map_url}: {e}")
            return None

def try_fetch_source_by_url(source_path, map_url):
    # attempt to fetch source by resolving relative to map_url
    try:
        candidate = urljoin(map_url, source_path)
        r = session.get(candidate, timeout=20)
        if r.status_code == 200 and r.text.strip():
            return r.text
    except Exception:
        pass
    return None

# MAIN
html, final_page_url = get_text(page_url)
script_entries = find_scripts_from_html(html, final_page_url)
print(f"Found {len(script_entries)} script entries on {final_page_url}")

processed_maps = 0
saved_files = 0

for entry in script_entries:
    if isinstance(entry, dict) and entry.get("inline"):
        js_text = entry.get("content", "")
        # try to find sourceMappingURL in inline script
        sm = extract_mapping_reference(js_text)
        js_base = final_page_url
        print(f"Inline script mapping: {sm}")
        if not sm:
            continue
        sm_json = handle_map_url(sm, js_base)
        if not sm_json:
            continue
        processed_maps += 1
        src_root = sm_json.get("sourceRoot", "")
        sources = sm_json.get("sources", [])
        contents = sm_json.get("sourcesContent", [])
        for i, src in enumerate(sources):
            filename = src
            if src_root:
                filename = os.path.join(src_root, src)
            # prefer sourcesContent
            content = None
            if contents and i < len(contents) and contents[i] is not None:
                content = contents[i]
            else:
                # try to fetch by URL
                content = try_fetch_source_by_url(src, final_page_url)
            if content is not None:
                save_file(filename, content)
                saved_files += 1
        continue

    # entry is a URL to a JS
    js_url = entry
    try:
        r = session.get(js_url, timeout=20)
        r.raise_for_status()
        js_text = r.text
        js_final_url = r.url
    except Exception as e:
        print(f"Failed to fetch JS {js_url}: {e}")
        continue

    sm = extract_mapping_reference(js_text)
    if not sm:
        print(f"No sourceMappingURL found in {js_url}")
        continue

    print(f"Found map reference for {js_url}: {sm}")
    sm_json = handle_map_url(sm, js_final_url)
    if not sm_json:
        print(f"Could not load map for {js_url}")
        continue

    processed_maps += 1
    src_root = sm_json.get("sourceRoot", "")
    sources = sm_json.get("sources", [])
    contents = sm_json.get("sourcesContent", [])

    # If sources are relative paths, join them sensibly and save
    for i, src in enumerate(sources):
        # Create a safe path
        # Some maps have absolute URLs in sources (e.g. webpack:///src/...) — clean that up
        cleaned = src
        # strip webpack:/// or file:///etc
        cleaned = re.sub(r'^[a-z]+:/{0,3}', '', cleaned)
        cleaned = cleaned.lstrip('/')
        if src_root:
            cleaned = os.path.join(src_root.strip('/'), cleaned)
        content = None
        if contents and i < len(contents) and contents[i] is not None:
            content = contents[i]
        else:
            # try to fetch the source using the map URL as base
            map_url_guess = urljoin(js_final_url, sm) if not sm.startswith("data:") else js_final_url
            content = try_fetch_source_by_url(src, map_url_guess)
        if content is None:
            print(f" - Could not obtain content for source: {src}")
            continue
        save_file(cleaned, content)
        saved_files += 1
        print(f" - Saved: {cleaned}")

print(f"Processed {processed_maps} maps, saved {saved_files} files to '{out_dir}'.")
