FROM python:3.12-slim

RUN pip install --no-cache-dir aiosmtpd requests

COPY relay.py /app/relay.py

EXPOSE 2525

CMD ["python", "-u", "/app/relay.py"]
