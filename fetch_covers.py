#!/usr/bin/env python3
"""
Stiahne obálky kníh z Google Books a Open Library pre audioknihy bez obrázkov.
Použitie: python3 fetch_covers.py [cesta_ku_kniznici]
"""

import json
import os
import re
import sys
import time
import unicodedata
import urllib.request
import urllib.parse
import urllib.error

BASE = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__)) + "/.."
COVERS_DIR = os.path.join(BASE, ".catalog", "covers")
os.makedirs(COVERS_DIR, exist_ok=True)

def slugify(name):
    return re.sub(r'[^a-zA-Z0-9]', '_', name)

def strip_diacritics(s):
    return ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
    )

def get_folders():
    """Vráti zoznam (author, title, slug) pre priečinky bez obálok."""
    folders = []
    for name in sorted(os.listdir(BASE)):
        path = os.path.join(BASE, name)
        if not os.path.isdir(path) or name.startswith('.') or ' - ' not in name:
            continue
        slug = slugify(name)
        cover_path = os.path.join(COVERS_DIR, slug + '.jpg')
        if os.path.exists(cover_path):
            continue
        author, title = name.split(' - ', 1)
        folders.append((author.strip(), title.strip(), slug))
    return folders

def fetch_json(url):
    """Stiahne JSON z URL."""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'AudiobookCatalog/1.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception:
        return None

def download_image(url, dest):
    """Stiahne obrázok do súboru."""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'AudiobookCatalog/1.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
            if len(data) < 1000:  # príliš malý = placeholder
                return False
            with open(dest, 'wb') as f:
                f.write(data)
            return True
    except Exception:
        return False

def try_google_books(author, title):
    """Skúsi Google Books API."""
    surname = author.split(',')[0].strip()
    query = f'{strip_diacritics(title)} {strip_diacritics(surname)}'
    url = 'https://www.googleapis.com/books/v1/volumes?q=' + urllib.parse.quote(query) + '&maxResults=3&printType=books'
    data = fetch_json(url)
    if not data or 'items' not in data:
        return None
    for item in data['items']:
        info = item.get('volumeInfo', {})
        links = info.get('imageLinks', {})
        # Preferuj väčší obrázok
        for key in ['thumbnail', 'smallThumbnail']:
            img_url = links.get(key)
            if img_url:
                # Google vracia http, zmeníme na https a zväčšíme
                img_url = img_url.replace('http://', 'https://')
                img_url = re.sub(r'zoom=\d', 'zoom=1', img_url)
                return img_url
    return None

def try_open_library(author, title):
    """Skúsi Open Library Search API."""
    surname = author.split(',')[0].strip()
    query = f'{strip_diacritics(title)} {strip_diacritics(surname)}'
    url = 'https://openlibrary.org/search.json?q=' + urllib.parse.quote(query) + '&limit=3&fields=cover_i,title,author_name'
    data = fetch_json(url)
    if not data or not data.get('docs'):
        return None
    for doc in data['docs']:
        cover_id = doc.get('cover_i')
        if cover_id:
            return f'https://covers.openlibrary.org/b/id/{cover_id}-M.jpg'
    return None

def main():
    folders = get_folders()
    total = len(folders)
    found = 0
    failed = []

    print(f"Hľadám obálky pre {total} kníh bez obrázkov...\n")

    for i, (author, title, slug) in enumerate(folders, 1):
        dest = os.path.join(COVERS_DIR, slug + '.jpg')
        print(f"[{i}/{total}] {author} - {title} ... ", end='', flush=True)

        # Skúsime Google Books
        img_url = try_google_books(author, title)
        source = 'Google'

        # Fallback na Open Library
        if not img_url:
            img_url = try_open_library(author, title)
            source = 'OpenLibrary'

        if img_url and download_image(img_url, dest):
            print(f"OK ({source})")
            found += 1
        else:
            print("nenájdená")
            failed.append(f"{author} - {title}")
            # Vymaž prípadný prázdny súbor
            if os.path.exists(dest) and os.path.getsize(dest) < 1000:
                os.remove(dest)

        # Rate limiting
        time.sleep(0.5)

    print(f"\nHotovo: {found}/{total} obálok stiahnutých.")
    if failed:
        print(f"\nNenájdené ({len(failed)}):")
        for f in failed:
            print(f"  - {f}")

if __name__ == '__main__':
    main()
