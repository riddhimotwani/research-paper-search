import csv, json, re, shutil, time, os, getpass, urllib.parse, urllib.request
from pathlib import Path

CSV_PATH = Path("data/research_papers.csv")
TARGET_TOTAL = 150
PER_QUERY = 35
USER_AGENT = "ResearchGraphStudentProject/1.0"
OPENALEX_API_KEY = os.getenv("OPENALEX_API_KEY") or getpass.getpass("OpenAlex API key (input hidden): ").strip()

SEARCH_TERMS = [
    "machine learning", "deep learning", "natural language processing",
    "large language models", "computer vision", "generative artificial intelligence",
    "graph neural networks", "information retrieval", "explainable artificial intelligence",
    "reinforcement learning", "federated learning", "sustainable artificial intelligence"
]
ALIASES = {
    "id": ["paperid", "paper_id", "id", "sourceid"],
    "title": ["title", "papertitle", "researchpaper", "name"],
    "authors": ["authors", "author", "researchers"],
    "year": ["year", "publicationyear", "publishedyear"],
    "venue": ["venue", "journal", "conference", "source", "publicationvenue"],
    "methods": ["methods", "method", "methodologies", "techniques"],
    "datasets": ["datasets", "dataset"],
    "keywords": ["keywords", "keyword", "topics", "concepts"],
    "abstract": ["abstract", "summary", "description"],
    "doi": ["doi"],
    "url": ["url", "paperurl", "link", "paperlink", "sourceurl"],
    "citations": ["citations", "citedbycount", "citationcount"],
}
METHOD_TERMS = [
    "transformer", "bert", "gpt", "convolutional neural network", "cnn",
    "recurrent neural network", "rnn", "lstm", "gru", "random forest",
    "support vector machine", "svm", "decision tree", "xgboost", "gradient boosting",
    "k-means", "dbscan", "reinforcement learning", "federated learning",
    "graph neural network", "gnn", "diffusion model", "gan", "variational autoencoder",
    "retrieval augmented generation", "rag", "contrastive learning",
    "self-supervised learning", "fine-tuning", "prompting", "quantization"
]
DATASET_TERMS = [
    "imagenet", "cifar-10", "cifar-100", "mnist", "fashion-mnist", "glue",
    "superglue", "squad", "wikitext", "common crawl", "laion", "ms coco",
    "coco", "pascal voc", "librispeech", "speech commands", "mmlu", "gsm8k",
    "humaneval", "bigbench"
]

def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())

def find_col(headers, key):
    aliases = {norm(x) for x in ALIASES[key]}
    return next((h for h in headers if norm(h) in aliases), None)

def abstract_text(index):
    if not index:
        return ""
    positions = {}
    for word, offsets in index.items():
        for offset in offsets:
            positions[offset] = word
    return " ".join(positions[i] for i in sorted(positions))

def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=45) as response:
        return json.loads(response.read().decode("utf-8"))

def matches(text, terms):
    low = (text or "").lower()
    return [term for term in terms if term in low][:8]

def fetch_openalex():
    records = {}
    for term in SEARCH_TERMS:
        params = {
            "search": term, "per-page": str(PER_QUERY),
            "sort": "cited_by_count:desc",
            "select": "id,doi,display_name,publication_year,authorships,primary_location,keywords,abstract_inverted_index,type,cited_by_count",
            "api_key": OPENALEX_API_KEY
        }
        url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
        print("Fetching:", term)
        try:
            payload = get_json(url)
        except Exception as exc:
            print("Fetch warning:", exc)
            continue
        for work in payload.get("results", []):
            title = (work.get("display_name") or "").strip()
            if not title:
                continue
            doi = (work.get("doi") or "").strip().lower()
            key = doi or norm(title)
            if key in records:
                continue
            authors = []
            for authorship in work.get("authorships", []):
                name = (authorship.get("author") or {}).get("display_name")
                if name and name not in authors:
                    authors.append(name)
            source = ((work.get("primary_location") or {}).get("source") or {})
            keywords = [k.get("display_name", "") for k in work.get("keywords", []) if k.get("display_name")]
            abstract = abstract_text(work.get("abstract_inverted_index"))
            text = " ".join([title, abstract, " ".join(keywords)])
            records[key] = {
                "id": "", "title": title, "authors": "; ".join(authors),
                "year": work.get("publication_year") or "",
                "venue": source.get("display_name") or "",
                "methods": "; ".join(matches(text, METHOD_TERMS)),
                "datasets": "; ".join(matches(text, DATASET_TERMS)),
                "keywords": "; ".join(keywords[:12]), "abstract": abstract,
                "doi": doi, "url": doi or work.get("id", ""),
                "citations": work.get("cited_by_count", "")
            }
        print("Unique works collected:", len(records))
        if len(records) >= TARGET_TOTAL + 25:
            break
        time.sleep(0.2)
    return list(records.values())

def main():
    if not CSV_PATH.exists():
        raise SystemExit("Run this from the ResearchGraph project folder; data/research_papers.csv was not found.")
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        headers, existing = reader.fieldnames or [], list(reader)
    if not headers:
        raise SystemExit("The CSV has no header row.")
    columns = {key: find_col(headers, key) for key in ALIASES}
    if not columns["title"]:
        raise SystemExit("Could not identify the title column. CSV headers: " + repr(headers))
    print("Existing papers:", len(existing))
    fetched = fetch_openalex()
    known = set()
    for row in existing:
        doi = (row.get(columns["doi"], "") if columns["doi"] else "").strip().lower()
        title = (row.get(columns["title"], "") or "").strip()
        known.add(doi or norm(title))
    additions = []
    for record in fetched:
        key = record["doi"] or norm(record["title"])
        if key in known:
            continue
        record["id"] = f"P{len(existing) + len(additions) + 1:03d}"
        row = {header: "" for header in headers}
        for field, column in columns.items():
            if column:
                row[column] = record.get(field, "")
        additions.append(row)
        known.add(key)
        if len(existing) + len(additions) >= TARGET_TOTAL:
            break
    backup = CSV_PATH.with_name("research_papers_backup_before_expansion.csv")
    shutil.copy2(CSV_PATH, backup)
    with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(existing + additions)
    total = len(existing) + len(additions)
    print("\nExpansion finished. Existing:", len(existing), "Added:", len(additions), "Total:", total)
    print("Backup:", backup)
    if total < TARGET_TOTAL:
        print("WARNING: Fewer than 150 records were returned. Rerun later or add more search terms.")
    print("Metadata source: OpenAlex. Method/dataset tags are keyword matches and need review.")

if __name__ == "__main__":
    main()
