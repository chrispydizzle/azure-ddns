FROM python:3.11-slim

WORKDIR /app

# Install cron and other dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY dnsupdate.py .

# Create a script to run the update and handle environment variables
RUN echo '#!/bin/bash' > /app/run_update.sh && \
    echo 'cd /app' >> /app/run_update.sh && \
    echo '/usr/local/bin/python dnsupdate.py' >> /app/run_update.sh && \
    chmod +x /app/run_update.sh

# Create crontab file - runs every 6 hours
#RUN echo ' */6 * * * /app/run_update.sh >> /var/log/ddns-update.log 2>&1' > /etc/cron.d/ddns-cron && \
RUN echo '*/1 * * * * /app/run_update.sh >> /var/log/ddns-update.log 2>&1' > /etc/cron.d/ddns-cron && \
chmod 0644 /etc/cron.d/ddns-cron && \
    crontab /etc/cron.d/ddns-cron

# Create log file
RUN touch /var/log/ddns-update.log

# Create startup script that runs once then starts cron
RUN echo '#!/bin/bash' > /app/start.sh && \
    echo 'echo "Running initial DNS update..."' >> /app/start.sh && \
    echo '/app/run_update.sh' >> /app/start.sh && \
    echo 'echo "Starting cron daemon..."' >> /app/start.sh && \
    echo 'cron -f &' >> /app/start.sh && \
    echo 'tail -f /var/log/ddns-update.log' >> /app/start.sh && \
    chmod +x /app/start.sh

# Run the startup script
CMD ["/app/start.sh"]

