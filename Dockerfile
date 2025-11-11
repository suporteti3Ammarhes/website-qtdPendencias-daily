FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
  curl \
  gnupg \
  unixodbc \
  unixodbc-dev \
  && rm -rf /var/lib/apt/lists/*

# Install Microsoft ODBC Driver for SQL Server
RUN curl https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
  && curl https://packages.microsoft.com/config/debian/12/prod.list > /etc/apt/sources.list.d/mssql-release.list \
  && apt-get update \
  && ACCEPT_EULA=Y apt-get install -y msodbcsql18 \
  && ACCEPT_EULA=Y apt-get install -y mssql-tools18 \
  && echo 'export PATH="$PATH:/opt/mssql-tools18/bin"' >> ~/.bashrc \
  && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p output logs static/css static/js

# Expose port
EXPOSE 5000

# Run the web application
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "app:app"]