# ResearchGraph — AI/ML Research Paper Search and Recommendation

A Streamlit + Neo4j Aura microproject prototype. It stores papers and their relationships to authors, methods, datasets, keywords and venues.

## 1. Requirements
- Python 3.10+
- Neo4j AuraDB instance and its connection URI, username and password
- VS Code (recommended)

## 2. Setup
```powershell
cd ResearchGraph
py -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
```
Open `.env` and fill in the values copied from your Neo4j Aura instance:
- `NEO4J_URI` — starts with `neo4j+s://`
- `NEO4J_USERNAME`
- `NEO4J_PASSWORD`
- `NEO4J_DATABASE` — normally `neo4j`

Do not share `.env`, commit it to Git, or paste your password into chat.

## 3. Import the sample graph
```powershell
python -c "from graph import get_driver, import_csv; d=get_driver(); print('Imported records:', import_csv(d)); d.close()"
```
You can also click **Import / refresh sample dataset** in the Streamlit sidebar.

## 4. Run the application
```powershell
streamlit run app.py
```
Open the local URL printed in the terminal (normally http://localhost:8501).

## 5. Graph model
Nodes: `Paper`, `Author`, `Method`, `Dataset`, `Keyword`, `Venue`.

Relationships:
- `(Paper)-[:AUTHORED_BY]->(Author)`
- `(Paper)-[:USES_METHOD]->(Method)`
- `(Paper)-[:EVALUATED_ON]->(Dataset)`
- `(Paper)-[:HAS_KEYWORD]->(Keyword)`
- `(Paper)-[:PUBLISHED_IN]->(Venue)`
- `(Paper)-[:RELATED_TO]->(Paper)` — derived when papers share methods, datasets or keywords; this is not a citation claim.

The Paper node stores the source URL and a concise project summary. Relationship paths therefore remain traceable to a source paper.

## 6. Sample questions
1. Find papers using CNN for image classification.
2. Find papers associated with Transformer.
3. Which papers use ImageNet?
4. Find papers related to Natural Language Processing.
5. Which methods are associated with Computer Vision?
6. Find papers authored by Alex Krizhevsky.
7. Find papers published in 2020 or later.
8. Which papers use CIFAR-10?
9. Find papers about Question Answering.
10. Which papers use BERT?
11. Find papers that share a method with a selected paper.
12. Which papers share datasets?
13. Find papers related to model optimization.
14. Find papers using retrieval-augmented generation.
15. Which papers connect Computer Vision and Deep Learning?

## 7. Important dataset note
The included CSV is a starter/demo catalogue, not a complete scholarly bibliographic dataset. Entries link to publisher/arXiv pages or DOI records. Check author lists, venue, dataset usage and publication year against each original source before final submission. The catalogue is manually curated and is not a comprehensive or automatically verified dataset.

## 8. Security
The Cypher console is a teaching/demo feature with basic query restrictions. It is not a security boundary. Keep the app local for the microproject. For deployment, create a dedicated Neo4j read-only user and use that account for retrieval. Keep import credentials separate from public-facing app credentials. Never expose Aura administrator credentials in a public app.

## 9. Current scope and extensions for the college cookbook
This starter includes graph construction, search, rule-based natural-language term matching, recommendations, visualization and a limited Cypher console. For a strict match to the supplied cookbook, extend it with:
- chunk-level source evidence / provenance,
- manually verified 15-question expected-vs-actual evaluation,
- precision/recall/F1 for extraction,
- comparison against a TF-IDF or vector baseline,
- screenshots and a reproducibility section.
