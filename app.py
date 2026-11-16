import streamlit as st
import pandas as pd
from pyvis.network import Network
import streamlit.components.v1 as components
from graph import (get_driver, import_csv, get_stats, search_papers,
                   get_filter_values, recommendations, graph_data,
                   get_paper_by_id, natural_language_search)

st.set_page_config(page_title="ResearchGraph", page_icon="🔎", layout="wide")
st.title("🔎 ResearchGraph")
st.caption("AI/ML Research Paper Search & Recommendation using Neo4j Knowledge Graphs")

@st.cache_resource
def connect():
    return get_driver()

try:
    driver = connect()
    st.sidebar.success("Connected to Neo4j Aura")
except Exception as e:
    st.error(f"Could not connect to Neo4j Aura: {e}")
    st.info("Create a .env file using .env.example and enter your Aura connection details.")
    st.stop()

with st.sidebar:
    st.header("Project controls")
    if st.button("Import / refresh sample dataset", use_container_width=True):
        try:
            count = import_csv(driver)
            st.success(f"Processed {count} sample paper records.")
            st.rerun()
        except Exception as e:
            st.error(f"Import failed: {e}")
    st.caption("Import is safe to repeat: MERGE prevents duplicate nodes with the same IDs/names.")
    page = st.radio("Navigate", ["Overview", "Research Explorer", "Recommendations", "Knowledge Graph", "Natural Language Search", "Cypher Console"])

if page == "Overview":
    st.subheader("Research knowledge at a glance")
    try:
        stats = get_stats(driver)
        cols = st.columns(4)
        for col, label, key in zip(cols, ["Papers","Authors","Methods","Datasets"],
                                   ["papers","authors","methods","datasets"]):
            col.metric(label, stats.get(key, 0))
        st.markdown("### What this system connects")
        st.write("Research papers ↔ authors ↔ methodologies ↔ datasets ↔ keywords ↔ publication venues.")
        st.markdown("### How retrieval works")
        st.write("Search filters identify matching graph nodes and return connected paper records. Recommendations rank other papers by shared methods, keywords and datasets.")
        st.info("Start by selecting **Import / refresh sample dataset** in the sidebar.")
    except Exception as e:
        st.error(str(e))

elif page == "Research Explorer":
    st.subheader("Find research papers")
    c1,c2,c3 = st.columns(3)
    text = c1.text_input("Search title, summary or term", placeholder="e.g. image classification")
    method = c2.selectbox("Methodology", ["All"] + get_filter_values(driver, "Method"))
    keyword = c3.selectbox("Keyword", ["All"] + get_filter_values(driver, "Keyword"))
    c4,c5 = st.columns(2)
    author = c4.selectbox("Author", ["All"] + get_filter_values(driver, "Author"))
    years = c5.slider("Publication year", 2010, 2025, (2010, 2025))
    if st.button("Search papers", type="primary"):
        rows = search_papers(driver, text=text, method="" if method=="All" else method,
                             keyword="" if keyword=="All" else keyword,
                             author="" if author=="All" else author,
                             year_from=years[0], year_to=years[1])
        st.session_state["search_results"] = rows
    rows = st.session_state.get("search_results", [])
    st.caption(f"{len(rows)} result(s)")
    for paper in rows:
        with st.container(border=True):
            st.markdown(f"**{paper['title']}** ({paper['year']})")
            st.write(paper.get("summary",""))
            st.caption("Authors: " + ", ".join(paper.get("authors", [])))
            st.caption("Methods: " + ", ".join(paper.get("methods", [])))
            st.caption("Datasets: " + ", ".join(paper.get("keywords", [])))
            st.markdown(f"[Open source paper]({paper.get('url','#')})")
            if st.button("Find related papers", key="rec_"+paper["paper_id"]):
                st.session_state["selected_paper"] = paper["paper_id"]
                st.session_state["page_recommend"] = True
    if st.session_state.get("page_recommend"):
        st.info("Open the Recommendations page from the sidebar to see related papers.")

elif page == "Recommendations":
    st.subheader("Discover related research")
    paper_rows, _ = __import__("graph").run_query(driver,
        "MATCH (p:Paper) RETURN p.paper_id AS id, p.title AS title ORDER BY title")
    options = {f"{r['title']} ({r['id']})": r["id"] for r in paper_rows}
    if options:
        default_id = st.session_state.get("selected_paper")
        labels = list(options.keys())
        default_index = next((i for i,k in enumerate(labels) if options[k]==default_id), 0)
        selected = st.selectbox("Choose a paper", labels, index=default_index)
        paper_id = options[selected]
        if st.button("Recommend similar papers", type="primary"):
            st.session_state["recommendations"] = recommendations(driver, paper_id)
        for rec in st.session_state.get("recommendations", []):
            with st.container(border=True):
                st.markdown(f"**{rec['title']}** ({rec['year']})")
                st.write(rec["summary"])
                st.caption(f"Similarity score: {rec['score']} | Shared methods: {rec['shared_methods']} | Shared keywords: {rec['shared_keywords']} | Shared datasets: {rec['shared_datasets']}")
                st.markdown(f"[Open paper]({rec['url']})")
    else:
        st.warning("No papers found. Import the sample dataset first.")

elif page == "Knowledge Graph":
    st.subheader("Explore paper relationships")
    records = graph_data(driver, 100)
    net = Network(height="650px", width="100%", directed=True, bgcolor="#ffffff", font_color="#222222")
    net.barnes_hut()
    added = set()
    for r in records:
        pid = r.get("pid")
        ptitle = r.get("ptitle") or pid
        if pid and pid not in added:
            net.add_node(pid, label=ptitle[:34], title=ptitle, color="#4F8EF7", shape="dot")
            added.add(pid)
        if r.get("nname"):
            nid = f"{r.get('nlabel')}::{r.get('nname')}"
            if nid not in added:
                color = {"Author":"#65B891","Method":"#F2B84B","Dataset":"#B28DDB","Keyword":"#E58BB8","Venue":"#8C9AA8"}.get(r.get("nlabel"), "#AAAAAA")
                net.add_node(nid, label=str(r.get("nname"))[:28], title=f"{r.get('nlabel')}: {r.get('nname')}", color=color)
                added.add(nid)
            net.add_edge(pid, nid, label=r.get("rel") or "")
    if added:
        html = net.generate_html()
        components.html(html, height=680, scrolling=True)
    else:
        st.warning("Graph is empty. Import the sample dataset first.")
    st.caption("Blue = Paper; green = Author; yellow = Method; purple = Dataset; pink = Keyword; grey-blue = Venue.")

elif page == "Natural Language Search":
    st.subheader("Ask a research question")
    st.caption("This first version uses transparent rule-based matching against known graph terms; it does not use an LLM.")
    question = st.text_input("Your question", placeholder="Find papers using CNN for image classification")
    if st.button("Retrieve papers", type="primary") and question.strip():
        rows = natural_language_search(driver, question)
        st.session_state["nl_results"] = rows
        st.session_state["nl_question"] = question
    rows = st.session_state.get("nl_results", [])
    if rows:
        st.success(f"Retrieved {len(rows)} paper(s) for: {st.session_state.get('nl_question','')}")
        for paper in rows:
            with st.container(border=True):
                st.markdown(f"**{paper['title']}** ({paper['year']})")
                st.write(paper["summary"])
                st.caption("Methods: "+", ".join(paper["methods"])+" | Keywords: "+", ".join(paper["keywords"]))
                st.markdown(f"[Open source paper]({paper['url']})")
    elif st.session_state.get("nl_question"):
        st.warning("No matches. Try a known term such as CNN, Transformer, Computer Vision, Image Classification or BERT.")

elif page == "Cypher Console":
    st.subheader("Read-only Cypher console")
    st.warning("Use read-only MATCH/RETURN queries only. Do not expose this console publicly with administrator credentials.")
    example = "MATCH (p:Paper)-[:USES_METHOD]->(m:Method) WHERE m.name CONTAINS 'CNN' RETURN p.title AS Paper, p.year AS Year, m.name AS Method LIMIT 20"
    query = st.text_area("Cypher query", value=example, height=130)
    if st.button("Run query", type="primary"):
        normalized = " ".join(query.strip().upper().split())
        forbidden = ["CREATE ", "MERGE ", "DELETE ", "DETACH ", "SET ", "REMOVE ", "DROP ", "ALTER ", "GRANT ", "DENY ", "LOAD CSV", "CALL "]
        if not normalized.startswith("MATCH ") or any(token in normalized for token in forbidden) or ";" in query:
            st.error("For safety, this console accepts a single MATCH query only and blocks write/admin clauses.")
        elif "LIMIT" not in normalized:
            st.error("Please add a LIMIT clause (maximum 100 rows).")
        else:
            try:
                # A hard upper bound is applied by wrapping the user query.
                safe_query = f"CALL {{ {query} }} RETURN * LIMIT 100"
                from graph import run_query
                rows, summary = run_query(driver, safe_query)
                if rows:
                    st.dataframe(pd.DataFrame(rows), use_container_width=True)
                else:
                    st.info("Query returned no rows.")
            except Exception as e:
                st.error(f"Cypher error: {e}")

st.divider()
st.caption("ResearchGraph · Academic microproject prototype · Verify source metadata before final academic submission.")
