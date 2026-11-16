
import os
import logging
from dotenv import load_dotenv
from neo4j import GraphDatabase

logging.basicConfig(level=logging.DEBUG)

load_dotenv()

uri = os.getenv("NEO4J_URI")
username = os.getenv("NEO4J_USERNAME")
password = os.getenv("NEO4J_PASSWORD")
database = os.getenv("NEO4J_DATABASE", "neo4j")

print("Testing Neo4j Aura...")
print("URI:", uri)
print("Username:", username)
print("Database:", database)

driver = None

try:
    driver = GraphDatabase.driver(
        uri,
        auth=(username, password)
    )

    driver.verify_connectivity()

    with driver.session(database=database) as session:
        result = session.run("RETURN 1 AS test").single()
        print("Query result:", result["test"])

    print("SUCCESS: Neo4j connected!")

except Exception as e:
    print("\nCONNECTION FAILED")
    print("Error type:", type(e).__name__)
    print("Error details:", repr(e))

finally:
    if driver:
        driver.close()
