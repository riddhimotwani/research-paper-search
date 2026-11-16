
# Load Windows trusted certificates into Python
import truststore
truststore.inject_into_ssl()

import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv(override=True)

uri = os.getenv("NEO4J_URI")
username = os.getenv("NEO4J_USERNAME")
password = os.getenv("NEO4J_PASSWORD")
database = os.getenv("NEO4J_DATABASE", "neo4j")

driver = None

try:
    print("Testing Neo4j using Windows certificate store...")

    driver = GraphDatabase.driver(
        uri,
        auth=(username, password)
    )

    driver.verify_connectivity()

    with driver.session(database=database) as session:
        result = session.run("RETURN 1 AS test").single()
        print("Query result:", result["test"])

    print("SUCCESS: Secure Neo4j connection established!")

except Exception as e:
    print("CONNECTION FAILED")
    print(type(e).__name__, str(e))

finally:
    if driver:
        driver.close()
