FROM python:3.11-slim

WORKDIR /app

# Install dependencies first — separate layer, cached unless
# requirements.txt changes, speeds up rebuilds during development
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy pipeline source
COPY main.py config.py ingest.py clean.py analyse.py detect.py \
     visualise.py export.py html_export.py narrative.py ./

# Runtime directories — created here so volume mounts have
# somewhere to attach even on first run
RUN mkdir -p data output output/charts logs

ENTRYPOINT ["python", "main.py"]
CMD ["--help"]
