cd ~/Sonya
# Live test: Соня сама пишет plugin для нового capability.
# Задача — IMAP email reader. Stub-credentials: достаточно чтобы plugin
# скомпилировался + зарегистрировался + дал sane response на missing creds.
TOKEN="1990"
BODY='{"text": "У меня к тебе capability test. Сейчас у тебя нет тула для чтения email. Напиши plugin email_reader через `plugins.create` который умеет: 1) импортировать imaplib + email, 2) принимать args {host, port, user, pass, folder=INBOX, limit=5}, 3) подключаться по SSL, выбирать N последних писем, возвращать [{from, subject, date, body_preview}]. Если creds пустые — возвращай dict с ошибкой, не падай. После создания вызови plugins.list чтобы проверить что появился, и plugins.call email_reader {} чтобы убедиться что обрабатывает empty creds gracefully. В DONE напиши результат. Это smoke test, реальные creds не нужны."}'
curl -s -X POST "http://127.0.0.1:8877/api/atrium/dialog" \
  -H "X-Atrium-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d "$BODY"
echo
