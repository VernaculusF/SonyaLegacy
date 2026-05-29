# WPScan CLI Scanner — Summary

Source: https://wpscan.com/wordpress-cli-scanner/ (fetched 2026-05-29)

**WPScan CLI** — black box WordPress security scanner для пентестеров и администраторов сайтов. Использует базу из **43,472 WordPress уязвимостей**.

## Что проверяет WPScan:
- Версия WordPress и связанные CVE
- Установленные плагины и их уязвимости
- Установленные темы и их уязвимости
- Username enumeration (через author archives, REST API, oEmbed)
- Слабые пароли через password brute forcing (xmlrpc.php, wp-login.php)
- Backed up / publicly accessible wp-config.php files
- Database dumps (SQL-файлы) в открытом доступе
- Exposed error logs от плагинов
- Media file enumeration
- Уязвимые Timthumb файлы
- WordPress readme file presence
- WP-Cron enabled
- User registration enabled
- Full Path Disclosure
- Upload directory listing
- И многое другое

## Установка