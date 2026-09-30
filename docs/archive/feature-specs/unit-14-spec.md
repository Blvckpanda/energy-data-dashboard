# Unit 14: Dockerize

## Goal

Add a `Dockerfile` so the pipeline can run in a single reproducible
container with no local Python or virtual environment setup required
— input data mounted in, reports and charts mounted back out to the
host filesystem.

---

## Implementation

### 1. `Dockerfile`

```dockerfile
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
```

**Why `python:3.11-slim` not full `python:3.11`:** slim omits build
tools and docs not needed at runtime — smaller image, faster pulls.
Matplotlib's `Agg` backend (already configured since Unit 5) doesn't
need a display server or system graphics libraries, so slim is
sufficient — no additional `apt-get` packages required.

**Why copy files individually instead of `COPY . .`:** keeps the
image minimal and explicit about what's actually needed at runtime.
`tests/`, `context/`, `docs/`, and `.git/` never need to be inside
the container.

---

### 2. `.dockerignore`

```
.venv/
__pycache__/
*.pyc
.git/
.github/
data/
output/
logs/
tests/
docs/
context/
*.md
.pytest_cache/
```

Even though the `Dockerfile` above only copies specific files, keep
this for safety — it prevents accidental inclusion if `COPY . .` is
ever used during future edits.

---

### 3. Build and Run Instructions

**Build the image:**

```bash
docker build -t energy-dashboard .
```

**Run with mounted volumes (PowerShell):**

```powershell
docker run --rm `
  -v ${PWD}/data:/app/data `
  -v ${PWD}/output:/app/output `
  -v ${PWD}/logs:/app/logs `
  energy-dashboard --file data/turbine.csv
```

**Run with mounted volumes (bash / macOS / Linux):**

```bash
docker run --rm \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/output:/app/output \
  -v $(pwd)/logs:/app/logs \
  energy-dashboard --file data/turbine.csv
```

**Why `--rm`:** the container is disposable — it does its job and
exits. Nothing persists inside the container itself; everything that
matters is written to the mounted host volumes.

**Why three separate `-v` mounts instead of mounting the whole
project:** mirrors the existing gitignore boundary — only the three
directories that actually need to exchange data between host and
container are mounted. `data/` in (read), `output/` and `logs/` out
(write). The container never touches source files.

---

### 4. Update `README.md` — Add Docker Section

Add a new section after **Install**, before **Usage**:

```markdown
## Run with Docker

No local Python setup required.

**Build:**
​```bash
docker build -t energy-dashboard .
​```

**Run (PowerShell):**
​```powershell
docker run --rm `
  -v ${PWD}/data:/app/data `
  -v ${PWD}/output:/app/output `
  -v ${PWD}/logs:/app/logs `
  energy-dashboard --file data/turbine.csv
​```

**Run (bash):**
​```bash
docker run --rm \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/output:/app/output \
  -v $(pwd)/logs:/app/logs \
  energy-dashboard --file data/turbine.csv
​```
```

---

## Dependencies

- Docker Desktop must be installed and running on your machine.
  This is a one-time human setup step, not something the agent
  can do — if Docker isn't installed, download it from
  docker.com before starting this unit.

No new Python packages — the container installs the existing
`requirements.txt` exactly as-is.

---

## Verify When Done

### Build
- [ ] `docker build -t energy-dashboard .` completes without errors
- [ ] `docker images` shows `energy-dashboard` with a reasonable
      size (expect roughly 200–400 MB — slim base + pandas/matplotlib
      is not tiny, but should not be gigabytes)

### Help and Argument Passing
- [ ] `docker run --rm energy-dashboard` (no args) shows the
      `--help` output — confirms the default `CMD` works
- [ ] `docker run --rm energy-dashboard --help` also shows help
      output explicitly

### Real Run — Critical
- [ ] Place `turbine.csv` in your local `data/` folder
- [ ] Run the full mounted-volume command from §3 above
- [ ] After the container exits, a real `.xlsx` report appears in
      your **host** `output/` folder — not just inside the container
- [ ] `logs/data_quality.log` on the host gains a new entry
- [ ] Charts appear in host `output/charts/`

### Isolation
- [ ] Delete your local `.venv/` entirely, confirm you can still
      run the pipeline successfully via Docker alone — proves the
      container is truly self-sufficient
- [ ] `docker run` on a fresh clone of the repo (no prior `pip
      install` on the host at all) still works end-to-end

### README
- [ ] Docker section renders correctly on GitHub with proper code
      block syntax highlighting for both PowerShell and bash
      variants
