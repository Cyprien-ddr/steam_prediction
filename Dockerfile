FROM mongo:7.0 AS mongo-tools
FROM python:3.12-slim
COPY --from=mongo-tools /usr/bin/mongodump /usr/bin/mongodump
COPY --from=mongo-tools /usr/bin/mongorestore /usr/bin/mongorestore
WORKDIR /app
RUN apt-get update && apt-get install -y \
    libssl3 \
    libkrb5-3 \
    libgssapi-krb5-2 \
    && rm -rf /var/lib/apt/lists/*
COPY . .
RUN pip install --no-cache-dir -r requirements.txt
CMD ["python", "-u", "main.py"]