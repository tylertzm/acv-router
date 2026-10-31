import csv
import html
import json
import os
import re
import ssl
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7'
}

# Regex patterns
phone_regex = re.compile(
    r'(?:telefon|tel\.?|fon|phone|tel:)\s*[:.\-]?\s*(\+?[0-9][0-9\s\/\(\)\-\.]{5,25}[0-9])',
    re.IGNORECASE
)
fax_regex = re.compile(
    r'(?:telefax|fax-nr\.?|fax(?:\s*\(?\w+\)?)?)\s*[:.\-]?\s*(\+?[0-9][0-9\s\/\(\)\-\.]{5,25}[0-9])',
    re.IGNORECASE
)
email_regex = re.compile(
    r'[a-zA-Z0-9_.+-]+(?:\s*@\s*|\s*\[at\]\s*|\s*\(at\)\s*)[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+',
    re.IGNORECASE
)
desc_meta_regex = re.compile(
    r'<meta\s+(?:name|property)=["\'](?:description|og:description)["\']\s+content=["\']([^"\']+)["\']',
    re.IGNORECASE
)
desc_meta_regex_reverse = re.compile(
    r'<meta\s+content=["\']([^"\']+)["\']\s+(?:name|property)=["\'](?:description|og:description)["\']',
    re.IGNORECASE
)
title_regex = re.compile(r'<title[^>]*>([^<]+)</title>', re.IGNORECASE)

def clean_phone(val):
    if not val:
        return ""
    val = ' '.join(val.split()).strip()
    digits = re.sub(r'\D', '', val)
    if 6 <= len(digits) <= 20:
        return val
    return ""

def clean_email(val):
    if not val:
        return ""
    val = val.replace(' [at] ', '@').replace('[at]', '@').replace(' (at) ', '@').replace('(at)', '@')
    val = val.replace(' ', '').strip().lower()
    if '@' in val and '.' in val.split('@')[-1]:
        return val
    return ""

def scrape_company_info(domain):
    data = {
        'phone': '',
        'fax': '',
        'email': '',
        'description': ''
    }
    if not domain:
        return data
        
    clean_domain = domain.strip().replace('https://', '').replace('http://', '').rstrip('/')
    base_domain = clean_domain.replace('www.', '').lower()
    
    urls = [
        f'https://{clean_domain}/',
        f'https://{clean_domain}/impressum',
        f'https://{clean_domain}/de/impressum',
        f'https://{clean_domain}/kontakt',
        f'https://{clean_domain}/de/kontakt'
    ]
    
    for url in urls:
        if data['phone'] and data['fax'] and data['email'] and data['description']:
            break
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=2.5, context=ctx) as resp:
                raw = resp.read(200000).decode('utf-8', errors='ignore')
                
                # 1. Description
                if not data['description']:
                    m_desc = desc_meta_regex.search(raw) or desc_meta_regex_reverse.search(raw)
                    if m_desc:
                        unescaped = html.unescape(m_desc.group(1))
                        cleaned_desc = ' '.join(unescaped.split())
                        if len(cleaned_desc) > 15:
                            data['description'] = cleaned_desc
                    elif url == f'https://{clean_domain}/':
                        m_title = title_regex.search(raw)
                        if m_title:
                            cleaned_title = ' '.join(html.unescape(m_title.group(1)).split())
                            if len(cleaned_title) > 10:
                                data['description'] = cleaned_title

                # 2. Phone
                if not data['phone']:
                    m_p = phone_regex.search(raw)
                    if m_p:
                        data['phone'] = clean_phone(m_p.group(1))
                        
                # 3. Fax
                if not data['fax']:
                    m_f = fax_regex.search(raw)
                    if m_f:
                        data['fax'] = clean_phone(m_f.group(1))
                        
                # 4. Email
                if not data['email']:
                    mailtos = re.findall(r'mailto:([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', raw, re.IGNORECASE)
                    valid_mailtos = [
                        m for m in mailtos 
                        if not any(x in m.lower() for x in ['sentry', 'wix', 'example', 'domain', 'cookie', 'cloudflare'])
                    ]
                    if valid_mailtos:
                        pref = [m for m in valid_mailtos if base_domain in m.lower()]
                        data['email'] = clean_email(pref[0] if pref else valid_mailtos[0])
                    else:
                        emails = email_regex.findall(raw)
                        valid_emails = [
                            m for m in emails 
                            if not any(x in m.lower() for x in ['sentry', 'wix', 'example', 'png', 'jpg', 'jpeg', 'svg', 'gif'])
                        ]
                        if valid_emails:
                            pref = [m for m in valid_emails if base_domain in m.lower()]
                            data['email'] = clean_email(pref[0] if pref else valid_emails[0])
                            
        except Exception:
            continue
            
    return data

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_csv = os.path.join(script_dir, '../data/dach_handwerker_hvac_828_leads.csv')
    if not os.path.exists(input_csv):
        input_csv = os.path.join(script_dir, 'dach_handwerker_hvac_828_leads.csv')
    if not os.path.exists(input_csv):
        input_csv = '/Users/tyler/Documents/lusha/dach_handwerker_hvac_828_leads.csv'

    output_csv = os.path.join(script_dir, 'lusha_dach_handwerker_hvac_828_leads.csv')
    cache_json = os.path.join(script_dir, 'scraped_cache.json')
    
    with open(input_csv, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        
    print(f"Loaded {len(rows)} leads. Starting multithreaded extraction (40 workers)...")
    start_time = time.time()
    
    results = {}
    with ThreadPoolExecutor(max_workers=40) as executor:
        future_to_idx = {
            executor.submit(scrape_company_info, row['Domain']): i
            for i, row in enumerate(rows)
        }
        
        completed = 0
        has_phone_count = 0
        has_fax_count = 0
        has_email_count = 0
        has_desc_count = 0
        
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                res = future.result()
            except Exception:
                res = {'phone': '', 'fax': '', 'email': '', 'description': ''}
            results[idx] = res
            
            if res['phone']: has_phone_count += 1
            if res['fax']: has_fax_count += 1
            if res['email']: has_email_count += 1
            if res['description']: has_desc_count += 1
            
            completed += 1
            if completed % 100 == 0 or completed == len(rows):
                print(f"Progress: {completed}/{len(rows)} | Phones: {has_phone_count} | Faxes: {has_fax_count} | Emails: {has_email_count} | Descs: {has_desc_count}", flush=True)
                
    elapsed = time.time() - start_time
    print(f"\nScraping complete in {elapsed:.1f}s!", flush=True)
    print(f"Summary: Phones: {has_phone_count}/{len(rows)} | Faxes: {has_fax_count}/{len(rows)} | Emails: {has_email_count}/{len(rows)} | Descs: {has_desc_count}/{len(rows)}", flush=True)
    
    # Save cache
    with open(cache_json, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
        
    # Export clean CSV specifically for Lusha platform import
    lusha_export = []
    for i, r in enumerate(rows):
        scraped = results.get(i, {'phone': '', 'fax': '', 'email': '', 'description': ''})
        
        phone = scraped.get('phone', '')
        fax = scraped.get('fax', '')
        email = scraped.get('email', '')
        desc = scraped.get('description', '')
        
        loc = r.get('Location', r.get('Full Location', ''))
        
        lusha_export.append({
            'Company Name': r['Company Name'],
            'Company Domain': r['Domain'],
            'Phone Number': phone,
            'Fax Number': fax,
            'Email': email,
            'Company Description': desc,
            'Country': r.get('Country', ''),
            'State': r.get('State', ''),
            'City': r.get('City', ''),
            'Location': loc,
            'Country Code': r.get('Country Code', ''),
            'Employee Headcount': r.get('Employee Headcount', ''),
            'Sub-Industry': r.get('Sub-Industry', 'Specialty Trade Contractors (Handwerk)'),
            'Trade Focus': r.get('Trade Focus', 'HVAC / Klimatechnik Installation & Trades'),
            'Company LinkedIn': r.get('LinkedIn', ''),
            'Lusha ID': r.get('Lusha ID', '')
        })
        
    fieldnames = [
        'Company Name',
        'Company Domain',
        'Phone Number',
        'Fax Number',
        'Email',
        'Company Description',
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
        writer.writerows(lusha_export)
        
    print(f"Successfully generated Lusha-ready CSV: {output_csv}", flush=True)

if __name__ == '__main__':
    main()
