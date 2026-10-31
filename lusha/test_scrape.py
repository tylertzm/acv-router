import urllib.request
import re
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

test_domains = [
    'www.hwp-handwerkspartner.de',
    'www.salvia-gebaeudetechnik.de',
    'www.ottoindustries.com',
    'www.zhb.de',
    'www.gebrueder-peters.de'
]

phone_regex = re.compile(r'(?:telefon|tel\.?|fon|phone|tel:)\s*[:.\-]?\s*(\+?[0-9][0-9\s\/\(\)\-\.]{5,25}[0-9])', re.IGNORECASE)
fax_regex = re.compile(r'(?:telefax|fax-nr\.?|fax(?:\s*\(?\w+\)?)?)\s*[:.\-]?\s*(\+?[0-9][0-9\s\/\(\)\-\.]{5,25}[0-9])', re.IGNORECASE)
email_regex = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
desc_regex = re.compile(r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']+)["\']', re.IGNORECASE)
og_desc_regex = re.compile(r'<meta\s+property=["\']og:description["\']\s+content=["\']([^"\']+)["\']', re.IGNORECASE)

for d in test_domains:
    phone, fax, email, desc = '', '', '', ''
    
    # Check Homepage
    try:
        req = urllib.request.Request(f'https://{d}', headers=headers)
        with urllib.request.urlopen(req, timeout=3.5, context=ctx) as resp:
            html = resp.read(250000).decode('utf-8', errors='ignore')
            m_desc = desc_regex.search(html) or og_desc_regex.search(html)
            if m_desc:
                desc = ' '.join(m_desc.group(1).split())
    except Exception:
        pass

    # Check Impressum and Kontakt
    urls = [f'https://{d}/impressum', f'https://{d}/kontakt', f'https://{d}']
    for u in urls:
        if phone and fax and email:
            break
        try:
            req = urllib.request.Request(u, headers=headers)
            with urllib.request.urlopen(req, timeout=3.5, context=ctx) as resp:
                raw = resp.read(250000).decode('utf-8', errors='ignore')
                
                if not phone:
                    m_p = phone_regex.search(raw)
                    if m_p:
                        cl = ' '.join(m_p.group(1).split())
                        if len(re.sub(r'\D', '', cl)) >= 6:
                            phone = cl
                if not fax:
                    m_f = fax_regex.search(raw)
                    if m_f:
                        cl = ' '.join(m_f.group(1).split())
                        if len(re.sub(r'\D', '', cl)) >= 6:
                            fax = cl
                if not email:
                    mailtos = re.findall(r'mailto:([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', raw, re.IGNORECASE)
                    if mailtos:
                        valid = [m for m in mailtos if not any(x in m.lower() for x in ['sentry', 'wix', 'example', 'domain', 'cookie'])]
                        if valid:
                            email = valid[0]
                    if not email:
                        all_emails = email_regex.findall(raw)
                        valid = [m for m in all_emails if not any(x in m.lower() for x in ['sentry', 'wix', 'example', 'png', 'jpg', 'jpeg'])]
                        if valid:
                            email = valid[0]
        except Exception:
            continue
            
    print('---', d)
    print('Phone:', phone)
    print('Fax:', fax)
    print('Email:', email)
    print('Desc:', desc[:120] + '...' if desc else 'None')
