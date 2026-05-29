"""Skill: skill-osint — OSINT methodology for pentesting target discovery.

Covers: Google dorks, Shodan, Censys, GitHub dorks, subdomain enumeration,
certificate transparency, technology fingerprinting.

Source: HackTricks External Recon Methodology (angelica.gitbook.io mirror).
"""

from __future__ import annotations

from typing import Any

SKILL_ID = "skill-osint"
SKILL_NAME = "osint"
SKILL_PURPOSE = "OSINT methodology: dorks, Shodan, Censys, subdomain discovery, certificate transparency."

OSINT_KB = r"""
# OSINT Pentesting Knowledge Base

## Google Dorks
- site:target.com → all indexed pages
- site:target.com filetype:pdf → documents
- site:target.com inurl:admin → admin panels
- site:target.com intitle:"index of" → open directories
- site:target.com intext:"password" → leaked passwords
- site:target.com ext:sql | ext:zip | ext:bak → backups
- site:target.com inurl:wp-content/plugins/ → WordPress plugins
- site:target.com "powered by" → technology fingerprint
- site:*.target.com -www → subdomains
- site:target.com inurl:login | inurl:signin → login pages

## Shodan
- hostname:target.com → basic search
- org:"Company Name" → by organisation
- ssl:"target.com" → SSL certificates
- port:443 http.title:"target" → HTTPS services
- http.component:"wordpress" → WP sites (for mass scanning)
- http.title:"phpmyadmin" → exposed phpMyAdmin
- product:"Apache httpd" country:"RU" → Apache servers in Russia
- Example query: http.title:"target" port:80,443,8080,8443

## Censys
- Web UI: https://search.censys.io
- Basic: target.com → certificate search
- Services: services.tls.certificates.leaf_data.subject.common_name: "target.com"

## GitHub Dorks
- "target.com" password → leaked credentials
- "target.com" api_key → API keys
- "target.com" secret → secrets
- "target.com" BEGIN RSA PRIVATE KEY → private keys
- "target.com" sql_password → DB passwords
- "target.com" s3_access_key → AWS keys
- org:targetorg → all repos of organisation

## Subdomain Enumeration
- Certificate Transparency: crt.sh → %.target.com
- subfinder -d target.com
- amass enum -d target.com
- assetfinder --subs-only target.com
- findomain -t target.com
- Google dork: site:*.target.com -www

## Technology Fingerprinting
- Wappalyzer browser extension
- whatweb target.com
- BuiltWith: https://builtwith.com/target.com
- Headers: curl -I https://target.com → Server, X-Powered-By, Set-Cookie
- Favicon hash: curl -s https://target.com/favicon.ico | python3 -c "import hashlib,sys;print(hashlib.md5(sys.stdin.buffer.read()).hexdigest())"

## Wayback Machine
- https://web.archive.org/web/*/target.com
- waybackurls target.com
- gau target.com (Get All URLs)

## DNS Enumeration
- dig any target.com
- dnsrecon -d target.com
- dnsdumpster.com → visual DNS map
- Zone transfer: dig axfr @ns1.target.com target.com
"""\


def run(context: dict[str, Any]) -> str:
    topic = (context.get("query") or context.get("user_input") or "").strip().lower()

    if not topic:
        return f"[skill-osint] OSINT methodology loaded. Ask about: google-dorks, shodan, censys, github, subdomains, fingerprint, wayback, dns."

    lines = OSINT_KB.split("\n")
    section_lines = []
    in_section = False

    for line in lines:
        if line.startswith("##") and topic.replace(" ", "-") in line.lower().replace(" ", "-"):
            in_section = True
            section_lines.append(line)
        elif line.startswith("##") and in_section:
            break
        elif in_section:
            section_lines.append(line)

    if section_lines:
        return "\n".join(section_lines)

    matched = [line for line in lines if topic in line.lower() and line.strip()]
    if matched:
        return f"[skill-osint] Found {len(matched)} lines matching '{topic}':\n" + "\n".join(matched[:30])

    return f"[skill-osint] Topic '{topic}' not found. Available: google-dorks, shodan, censys, github, subdomains, fingerprint, wayback, dns."