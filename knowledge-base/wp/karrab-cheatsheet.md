# WordPress Pentesting Cheatsheet — Karrab (Sep 2025)

Источник: https://karrab7.com/articles/WordPress-Pentesting-Cheatsheet

## Core Components
- **wp-content** — themes, plugins, uploads
- **wp-includes** — core libraries
- **wp-admin** — admin UI
- **wp-config.php** — DB credentials, salts, debug settings
- **.htaccess / web.config** — rewrite and access rules
- **readme.html, license.txt** — version leakage

## User Roles
- **Super Admin** — Multisite full control
- **Administrator** — Full single-site control (install plugins/themes, edit code)
- **Editor** — Manage all content
- **Author** — Write, publish own posts only
- **Contributor** — Write/edit own posts, cannot publish
- **Subscriber** — Profile only

## Enumeration

### Version detection
- `/wp-links-opml.php`
- `curl -s URL | grep WordPress`
- `<meta name="generator" content="WordPress X.Y.Z">`

### Juicy Endpoints (wordlist: karrab7 wp-karrab.txt)
- `/robots.txt`
- `/xmlrpc.php`
- `/wp-admin/`
- `/wp-login.php`
- `/wp-content/uploads/`
- `/wp-includes/`
- `/sitemap.xml`, `/wp-sitemap.xml`
- `/feed`, `/feed/atom/`
- `/wp-json/wp/v2/` — posts, pages, users, media
- `/wp-json/wp/v2/users` — user enumeration via REST API
- `/wp-json/wp/v2/media`
- `/wp-config.php.bak` — backup config with DB credentials

### XMLRPC Exploitation
- `xmlrpc.php` — legacy XML-RPC API
- **Pingback abuse:** SSRF, DDoS amplification
- **Brute-force:** `wp.getUsersBlogs`, `wp.getAuthors` — single request = multiple password attempts
- **User enumeration:** `system.listMethods`, `wp.getUsers`

## Attack Vectors
- Directory listing discovery in `/wp-content/uploads/`
- Theme editing for RCE (Appearance → Theme Editor → modify PHP files)
- Plugin vulnerabilities — check known CVEs for installed plugins
- Default credentials / weak passwords
- Backup files: `wp-config.php.bak`, `.sql` dumps in uploads