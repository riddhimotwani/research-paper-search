import os
from pathlib import Path
import pandas as pd
import truststore
truststore.inject_into_ssl()
from dotenv import load_dotenv
from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

def get_driver():
    uri = os.getenv("NEO4J_URI", "").strip()
    username = os.getenv("NEO4J_USERNAME", "").strip()
    password = os.getenv("NEO4J_PASSWORD", "").strip()
    if not all([uri, username, password]):
        raise RuntimeError("Neo4j credentials are missing. Copy .env.example to .env and fill in your Aura credentials.")
    driver = GraphDatabase.driver(uri, auth=(username, password))
    driver.verify_connectivity()
    return driver

def run_query(driver, query, **params):
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    records, summary, keys = driver.execute_query(
        query, parameters_=params, database_=database
    )
    return [record.data() for record in records], summary

def create_constraints(driver):
    queries = [
        "CREATE CONSTRAINT paper_id IF NOT EXISTS FOR (n:Paper) REQUIRE n.paper_id IS UNIQUE",
        "CREATE CONSTRAINT author_name IF NOT EXISTS FOR (n:Author) REQUIRE n.name IS UNIQUE",
        "CREATE CONSTRAINT method_name IF NOT EXISTS FOR (n:Method) REQUIRE n.name IS UNIQUE",
        "CREATE CONSTRAINT dataset_name IF NOT EXISTS FOR (n:Dataset) REQUIRE n.name IS UNIQUE",
        "CREATE CONSTRAINT keyword_name IF NOT EXISTS FOR (n:Keyword) REQUIRE n.name IS UNIQUE",
        "CREATE CONSTRAINT venue_name IF NOT EXISTS FOR (n:Venue) REQUIRE n.name IS UNIQUE",
    ]
    for q in queries:
        run_query(driver, q)

def import_csv(driver, csv_path=None):
    path = Path(csv_path) if csv_path else ROOT / "data" / "research_papers.csv"
    df = pd.read_csv(path).fillna("")
    create_constraints(driver)
    query = """
    MERGE (p:Paper {paper_id: $paper_id})
    SET p.title = $title, p.year = toInteger($year),
        p.summary = $summary, p.url = $url
    MERGE (v:Venue {name: $venue})
    MERGE (p)-[:PUBLISHED_IN]->(v)
    FOREACH (author_name IN $authors |
      MERGE (a:Author {name: author_name})
      MERGE (p)-[:AUTHORED_BY]->(a)
    )
    FOREACH (method_name IN $methods |
      MERGE (m:Method {name: method_name})
      MERGE (p)-[:USES_METHOD]->(m)
    )
    FOREACH (dataset_name IN $datasets |
      MERGE (d:Dataset {name: dataset_name})
      MERGE (p)-[:EVALUATED_ON]->(d)
    )
    FOREACH (keyword_name IN $keywords |
      MERGE (k:Keyword {name: keyword_name})
      MERGE (p)-[:HAS_KEYWORD]->(k)
    )
    """
    imported = 0
    for row in df.to_dict(orient="records"):
        params = {
            "paper_id": str(row["paper_id"]),
            "title": str(row["title"]),
            "year": int(row["year"]),
            "summary": str(row["summary"]),
            "url": str(row["url"]),
            "venue": str(row["venue"]),
            "authors": [x.strip() for x in str(row["authors"]).split("|") if x.strip()],
            "methods": [x.strip() for x in str(row["methods"]).split("|") if x.strip()],
            "datasets": [x.strip() for x in str(row["datasets"]).split("|") if x.strip()],
            "keywords": [x.strip() for x in str(row["keywords"]).split("|") if x.strip()],
        }
        run_query(driver, query, **params)
        imported += 1

    # Materialize an explicit RELATED_TO edge when two papers share methods,
    # datasets or keywords. This is a derived relation, not a citation claim.
    run_query(driver, """
    MATCH (p1:Paper)-[:HAS_KEYWORD|USES_METHOD|EVALUATED_ON]->(x)
          <-[:HAS_KEYWORD|USES_METHOD|EVALUATED_ON]-(p2:Paper)
    WHERE p1.paper_id < p2.paper_id
    WITH p1, p2, count(DISTINCT x) AS shared
    MERGE (p1)-[r:RELATED_TO]->(p2)
    SET r.shared_entities = shared,
        r.reason = 'Shares methods, datasets or keywords'
    """)
    return imported

def get_stats(driver):
    q = """
    MATCH (p:Paper)
    OPTIONAL MATCH (a:Author)
    WITH count(DISTINCT p) AS papers, count(DISTINCT a) AS authors
    MATCH (m:Method)
    WITH papers, authors, count(DISTINCT m) AS methods
    MATCH (d:Dataset)
    RETURN papers, authors, methods, count(DISTINCT d) AS datasets
    """
    rows, _ = run_query(driver, q)
    return rows[0] if rows else {"papers":0,"authors":0,"methods":0,"datasets":0}

def search_papers(driver, text="", method="", keyword="", author="", year_from=1900, year_to=2100, limit=50):
    q = """
    MATCH (p:Paper)
    OPTIONAL MATCH (p)-[:USES_METHOD]->(m:Method)
    OPTIONAL MATCH (p)-[:HAS_KEYWORD]->(k:Keyword)
    OPTIONAL MATCH (p)-[:AUTHORED_BY]->(a:Author)
    WITH p,
         collect(DISTINCT m.name) AS methods,
         collect(DISTINCT k.name) AS keywords,
         collect(DISTINCT a.name) AS authors
    WHERE p.year >= $year_from AND p.year <= $year_to
      AND ($text = "" OR toLower(p.title + " " + p.summary) CONTAINS toLower($text)
           OR any(x IN methods WHERE toLower(x) CONTAINS toLower($text))
           OR any(x IN keywords WHERE toLower(x) CONTAINS toLower($text)))
      AND ($method = "" OR any(x IN methods WHERE x = $method))
      AND ($keyword = "" OR any(x IN keywords WHERE x = $keyword))
      AND ($author = "" OR any(x IN authors WHERE x = $author))
    RETURN p.paper_id AS paper_id, p.title AS title, p.year AS year,
           p.summary AS summary, p.url AS url, methods, keywords, authors
    ORDER BY p.year DESC, p.title
    LIMIT $limit
    """
    rows, _ = run_query(driver, q, text=text, method=method, keyword=keyword,
                        author=author, year_from=int(year_from), year_to=int(year_to),
                        limit=int(limit))
    return rows

def get_filter_values(driver, label):
    allowed = {"Method":"Method", "Keyword":"Keyword", "Author":"Author"}
    if label not in allowed:
        return []
    rows, _ = run_query(driver, f"MATCH (n:{allowed[label]}) RETURN n.name AS name ORDER BY name")
    return [r["name"] for r in rows]

def recommendations(driver, paper_id, limit=8):
    q = """
    MATCH (source:Paper {paper_id:$paper_id})
    OPTIONAL MATCH (source)-[:USES_METHOD]->(sm:Method)<-[:USES_METHOD]-(candidate:Paper)
    OPTIONAL MATCH (source)-[:HAS_KEYWORD]->(sk:Keyword)<-[:HAS_KEYWORD]-(candidate)
    OPTIONAL MATCH (source)-[:EVALUATED_ON]->(sd:Dataset)<-[:EVALUATED_ON]-(candidate)
    WHERE candidate IS NOT NULL AND candidate.paper_id <> source.paper_id
    WITH candidate,
         count(DISTINCT sm) AS shared_methods,
         count(DISTINCT sk) AS shared_keywords,
         count(DISTINCT sd) AS shared_datasets
    WITH candidate, shared_methods, shared_keywords, shared_datasets,
         shared_methods*3 + shared_keywords + shared_datasets*2 AS score
    WHERE score > 0
    RETURN candidate.paper_id AS paper_id, candidate.title AS title,
           candidate.year AS year, candidate.summary AS summary,
           candidate.url AS url, score, shared_methods, shared_keywords, shared_datasets
    ORDER BY score DESC, year DESC
    LIMIT $limit
    """
    rows, _ = run_query(driver, q, paper_id=paper_id, limit=int(limit))
    return rows

def graph_data(driver, limit=60):
    q = """
    MATCH (p:Paper)
    OPTIONAL MATCH (p)-[r]-(n)
    WITH p, r, n
    WHERE n IS NULL OR (n:Author OR n:Method OR n:Dataset OR n:Keyword OR n:Venue)
    RETURN p.paper_id AS pid, p.title AS ptitle,
           type(r) AS rel, labels(n)[0] AS nlabel,
           coalesce(n.name, n.paper_id) AS nname
    LIMIT $limit
    """
    return run_query(driver, q, limit=int(limit))[0]

def get_paper_by_id(driver, paper_id):
    rows, _ = run_query(driver, """
    MATCH (p:Paper {paper_id:$paper_id})
    OPTIONAL MATCH (p)-[:AUTHORED_BY]->(a:Author)
    OPTIONAL MATCH (p)-[:USES_METHOD]->(m:Method)
    OPTIONAL MATCH (p)-[:EVALUATED_ON]->(d:Dataset)
    OPTIONAL MATCH (p)-[:HAS_KEYWORD]->(k:Keyword)
    RETURN p.paper_id AS paper_id, p.title AS title, p.year AS year,
           p.summary AS summary, p.url AS url,
           collect(DISTINCT a.name) AS authors,
           collect(DISTINCT m.name) AS methods,
           collect(DISTINCT d.name) AS datasets,
           collect(DISTINCT k.name) AS keywords
    """, paper_id=paper_id)
    return rows[0] if rows else None

def natural_language_search(driver, question):
    """Transparent rule-based intent mapping; not an LLM."""
    q = question.lower()
    method = ""
    keyword = ""
    author = ""
    methods = get_filter_values(driver, "Method")
    keywords = get_filter_values(driver, "Keyword")
    authors = get_filter_values(driver, "Author")
    for value in methods:
        if value.lower() in q:
            method = value
            break
    for value in keywords:
        if value.lower() in q:
            keyword = value
            break
    for value in authors:
        if value.lower() in q:
            author = value
            break
    return search_papers(driver, text="" if (method or keyword or author) else question,
                         method=method, keyword=keyword, author=author)
