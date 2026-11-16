// Run in Neo4j Aura Query tool only if you want to inspect the graph.
// Constraints are also created automatically by graph.py.
MATCH (n) RETURN labels(n) AS Labels, count(*) AS Count ORDER BY Count DESC;

MATCH ()-[r]->() RETURN type(r) AS Relationship, count(*) AS Count ORDER BY Count DESC;

MATCH (p:Paper)-[:USES_METHOD]->(m:Method)
WHERE toLower(m.name) CONTAINS 'cnn'
RETURN p.title, p.year, m.name
ORDER BY p.year DESC LIMIT 20;

MATCH (p1:Paper)-[:HAS_KEYWORD]->(k:Keyword)<-[:HAS_KEYWORD]-(p2:Paper)
WHERE p1.paper_id < p2.paper_id
RETURN p1.title, p2.title, k.name LIMIT 20;
