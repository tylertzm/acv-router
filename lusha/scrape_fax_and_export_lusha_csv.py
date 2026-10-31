import csv
import json
import re
import ssl
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7'
}

# Regex for German/Swiss/Austrian fax formats
# Matches "Telefax:", "Fax:", "Fax-Nr.:", "Fax", etc. followed by phone-like digits
fax_regex = re.compile(
    r'(?:telefax|fax-nr\.?|fax(?:\s*\(?\w+\)?)?)\s*[:.\-]?\s*(\+?[0-9][0-9\s\/\(\)\-\.]{5,25}[0-9])',
    re.IGNORECASE
)

def scrape_fax_for_domain(domain):
    if not domain:
        return ""
        
    clean_domain = domain.strip().replace('https://', '').replace('http://', '').rstrip('/')
    urls = [
        f'https://{clean_domain}/impressum',
        f'https://{clean_domain}/de/impressum',
        f'https://{clean_domain}/kontakt',
        f'https://{clean_domain}/de/kontakt',
        f'https://{clean_domain}/'
    ]
    
    for url in urls:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=3.5, context=ctx) as resp:
                # Limit read size to 250KB for fast processing
                raw = resp.read(250000).decode('utf-8', errors='ignore')
                
                # Check for fax match
                matches = fax_regex.findall(raw)
                for m in matches:
                    cleaned = ' '.join(m.split())
                    # Ensure it has enough digits to be a real fax (at least 6 digits)
                    digits = re.sub(r'\D', '', cleaned)
                    if 6 <= len(digits) <= 18:
                        return cleaned
        except Exception:
            continue
            
    # Try http if https failed
    try:
        req = urllib.request.Request(f'http://{clean_domain}/impressum', headers=headers)
        with urllib.request.urlopen(req, timeout=3.5, context=ctx) as resp:
            raw = resp.read(250000).decode('utf-8', errors='ignore')
            matches = fax_regex.findall(raw)
            for m in matches:
                cleaned = ' '.join(m.split())
                digits = re.sub(r'\D', '', cleaned)
                if 6 <= len(digits) <= 18:
                    return cleaned
    except Exception:
        pass
        
    return ""

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_csv = os.path.join(script_dir, '../data/dach_handwerker_hvac_828_leads.csv')
    if not os.path.exists(input_csv):
        input_csv = os.path.join(script_dir, 'dach_handwerker_hvac_828_leads.csv')
    if not os.path.exists(input_csv):
        input_csv = '/Users/tyler/Documents/lusha/dach_handwerker_hvac_828_leads.csv'

    output_csv = os.path.join(script_dir, 'lusha_import_dach_hvac_handwerker_with_fax.csv')
    
    with open(input_csv, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        
    print(f"Loaded {len(rows)} leads. Starting multithreaded fax scraping...")
    start_time = time.time()
    
    fax_results = {}
    with ThreadPoolExecutor(max_workers=25) as executor:
        future_to_idx = {
            executor.submit(scrape_fax_for_domain, row['Domain']): i
            for i, row in enumerate(rows)
        }
        
        completed = 0
        found_count = 0
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                fax = future.result()
            except Exception:
                fax = ""
            fax_results[idx] = fax
            if fax:
                found_count += 1
            completed += 1
            if completed % 100 == 0 or completed == len(rows):
                print(f"Progress: {completed}/{len(rows)} checked ({found_count} fax numbers found so far)...")
                
    elapsed = time.time() - start_time
    print(f"Scraping finished in {elapsed:.1f} seconds. Total Fax numbers found: {found_count}/{len(rows)}")
    
    # Prepare rows formatted specifically for Lusha CSV Import
    lusha_export_rows = []
    for i, r in enumerate(rows):
        fax = fax_results.get(i, '')
        lusha_export_rows.append({
            'Company Name': r['Company Name'],
            'Company Domain': r['Domain'],
            'Fax Number': fax,
            'Country': r['Country'],
            'State': r['State'],
            'City': r['City'],
            'Location': r['Full Location'],
            'Country Code': r['Country Code'],
            'Employee Headcount': r['Employee Headcount'],
            'Sub-Industry': r['Sub-Industry'],
            'Trade Focus': r['Trade Focus'],
            'Company LinkedIn': r['LinkedIn'],
            'Lusha ID': r['Lusha ID']
        })
        
    fieldnames = [
        'Company Name',
        'Company Domain',
        'Fax Number',
        'Country',
        'State',
        'City',
        'Location',
        'Country Code',
        'Employee Headcount',
        'Sub-Industry',
        'Trade Focus',
        'Company LinkedIn',
        'Lusha ID'
    ]
    
    with open(output_csv, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(lusha_export_rows)
        
    print(f"Exported clean Lusha-importable CSV to: {output_csv}")

if __name__ == '__main__':
    main()
