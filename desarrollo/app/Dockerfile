# Imagen del servidor web/aplicacion (frontal). Se levantan 2 replicas (WEB01/WEB02).
# Contexto de build = carpeta desarrollo/ (ver docker-compose.yml).
FROM python:3.11-slim

WORKDIR /app
COPY app/app.py app/seed.py /app/
COPY db/init.sql /db/init.sql

# La app busca el esquema en ../db/init.sql respecto a /app -> /db/init.sql
RUN mkdir -p /db && ln -sf /db/init.sql /init.sql
ENV DB_PATH=/data/intranet.db
ENV SCHEMA_PATH=/db/init.sql
EXPOSE 8001

CMD ["sh", "-c", "python seed.py && python app.py"]
