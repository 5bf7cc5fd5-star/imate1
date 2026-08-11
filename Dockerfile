FROM python:3.12-slim
WORKDIR /app
COPY server.py frontend.html admin.html ./
RUN mkdir -p data
COPY data/ ./data/
ENV PORT=8080
EXPOSE 8080
CMD ["python3", "server.py"]
