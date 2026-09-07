# HelparrSuite

HelparrSuite is a specialized collection of microservices designed to enhance and maintain media libraries in conjunction with the `*arr` ecosystem (Sonarr, Radarr) using local AI (Ollama).

---

## Suite Architecture & Port Map

| Service | Port | Description |
| :--- | :--- | :--- |
| **HelparrSuite Portal** | `6780` | Central dashboard and unified management interface *(planned)* |
| **DBarr** | `6781` | Core media database, multi-source metadata aggregator & subtitle/transcript vault |
| **Verifyarr** | `6782` | Automated verification, OCR file auditing, and episode consistency validator *(planned)* |
| **DLarr** | `6783` | Downloader & missing episode acquisition engine *(planned)* |

---

## DBarr (`6781`)

**DBarr** is the foundational database microservice. It:
1. Connects to **Sonarr** to discover and ingest monitored series.
2. Supports **single and multi-show batch import**.
3. Orders episodes strictly from **Season 1 through Season N**, concluding with **Specials (Season 0)**.
4. Locates and archives the episode's **native-language subtitle dialogue** as the canonical transcript.
5. Ingests and cross-maps external metadata sources (TMDB, TVmaze, OMDb) verified by local **Ollama LLMs**.
6. Exposes a clean REST API and database for downstream suite services.

---

## Docker Deployment

Images are automatically built and published to GitHub Container Registry (`ghcr.io`):
- `ghcr.io/eatprilosec/dbarr:latest`

### Compose Example
```yaml
services:
  dbarr:
    image: ghcr.io/eatprilosec/dbarr:latest
    container_name: dbarr
    restart: unless-stopped
    ports:
      - "6781:6781"
    environment:
      - DBARR_PORT=6781
      - DBARR_DATA_DIR=/config
      - TZ=UTC
    volumes:
      - /DockerData/dbarr/config:/config
```
