FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

RUN chmod +x start.sh

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8082

CMD ["./start.sh"]
