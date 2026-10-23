FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir --no-deps .

EXPOSE 8000

# Mount the classifier checkout and set CLASSIFIER_ROOT to that path.
# Pass OPENAI_API_KEY in the environment or with --env-file.
CMD ["python", "-m", "uvicorn", "genomic_evidence_agent.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
