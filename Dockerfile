FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN mkdir -p data && \
    (test -f data/users.json || echo "[]" > data/users.json) && \
    (test -f data/withdrawals.json || echo "[]" > data/withdrawals.json) && \
    (test -f users.json && cp users.json data/users.json || true) && \
    (test -f withdrawals.json && cp withdrawals.json data/withdrawals.json || true)
ENV PORT=8080
ENV PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["python3", "boot.py"]
