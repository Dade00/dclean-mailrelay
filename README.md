# dclean MailRelay

SMTP relay on the Railway private network that forwards mail to the Brevo HTTP API
(Railway blocks outbound SMTP on 25/465/587/2525).

Env: `BREVO_API_KEY`, `FROM_EMAIL`, `FROM_NAME`, `RELAY_PORT` (default 2525).
