FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN mkdir -p /app/data
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
EXPOSE 8080
CMD ["python3", "-u", "server.py"]
