# SEO Keyword Extractor (Persian EmbedRank)

Extracts the most relevant **Persian keyphrases** from web‑page content using
[EmbedRank](https://arxiv.org/abs/1801.04470): **hazm** POS‑tagging + noun‑phrase chunking to
generate candidates, embedding similarity (via an API) to rank them, and **MMR** to keep the
top keyphrases diverse. Clean **Material‑Design**, RTL (Persian) dashboard.

It reads page content from the **[SEO Content Reranker](https://github.com/miladshooli/seo-content-reranker)**
SQLite database (its sibling app) — pick a stored analysis and extract keywords for every URL in
it — or **upload a `.db` file**. Results export to a 3‑sheet **Excel** report.

This is the third in a family: [title scorer](https://github.com/miladshooli/seo-title-similarity-ranker)
→ [content reranker](https://github.com/miladshooli/seo-content-reranker) → **keyword extractor**.

![nlp](https://img.shields.io/badge/NLP-hazm%20POS%20%2B%20EmbedRank-7c3aed) ![embed](https://img.shields.io/badge/embeddings-Jina%20%2F%20Voyage-db2777)

---

## Why an embeddings API instead of a local model?

The original script used the local `sent2vec-naab` model (several GB → needs lots of RAM). This
version keeps the **same EmbedRank algorithm and hazm Persian POS tagging**, but pulls phrase
embeddings from **Jina** or **Voyage** (selectable in the UI). It runs on a tiny (~2 GB) VPS, needs
no multi‑GB download, and is multilingual. Markdown noise (`**`, `#`, links) is stripped from
content before tagging so keyphrases stay clean.

## How it works

```
page content ─▶ clean markdown ─▶ hazm normalize + POS tag ─▶ NP‑grammar candidates
                                                                     │
                                              Jina / Voyage embeddings (candidates + text)
                                                                     │
                                     cosine sim ─▶ EmbedRank + MMR (β=0.9) ─▶ top‑N keyphrases
```

Work runs in a **background thread**; the dashboard polls `/api/job/<id>` with a live log.

### Endpoints

- `GET  /api/sources` — analyses available in the server‑side reranker DB
- `POST /api/upload` — upload a `.db`; returns its analyses
- `POST /api/extract` — `{source, query_id, upload_id, provider, embed_key, keyword_num, max_chars}` → `{job_id}`
- `GET  /api/job/<id>` — status / progress / log / results
- `GET  /api/export/<job_id>` — Excel report (per‑URL keywords / top‑10 / cross‑page frequency)

## API keys

The embedding key (Jina **or** Voyage) is entered in the UI and stored in the browser. Optional
server‑side fallbacks: `JINA_API_KEY`, `VOYAGE_API_KEY`.

## Run locally

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# Persian POS model:
mkdir -p models && curl -sSL -o models/pos_tagger.model \
  https://huggingface.co/roshan-research/hazm-postagger/resolve/main/pos_tagger.model
export POS_MODEL=models/pos_tagger.model
python app.py          # http://localhost:8002
```

## Deploy (Debian/Ubuntu, behind nginx)

```bash
sudo bash deploy/setup.sh      # venv + hazm + POS model + systemd + nginx
sudo certbot --nginx -d your.domain.com --redirect
```

`deploy/setup.sh` creates the venv, installs deps, downloads the POS model, and wires up
systemd (gunicorn on `127.0.0.1:8002`) and nginx.

## Project layout

```
app.py                      Flask backend (hazm + EmbedRank + embeddings + jobs + Excel)
templates/index.html        Material‑Design RTL dashboard
requirements.txt            flask, gunicorn, requests, numpy, scikit-learn, hazm, openpyxl
deploy/
  seo-kwr.service           systemd unit (venv gunicorn, port 8002)
  nginx.conf                reverse proxy (64MB uploads; add HTTPS with certbot)
  setup.sh                  one-shot installer
```

## License

MIT — see [LICENSE](LICENSE).
