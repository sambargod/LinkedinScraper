import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import webbrowser
from datetime import datetime
import json
from pyvis.network import Network
import networkx as nx
import streamlit.components.v1 as components
import warnings
from collections import Counter
import re
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import nltk
from nltk.corpus import stopwords
nltk.download('stopwords')

# Suppress warnings
warnings.filterwarnings("ignore")

# ---------- Helper Functions ----------
def format_search_query(SQ):
    return SQ.replace(" ", "%20")

def get_links_from_body(url):
    list_links = []
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            body = soup.body
            if body:
                links = body.find_all('a')
                for link in links:
                    href = link.get('href')
                    heading = link.text
                    if href:
                        list_links.append((href, heading))
    except Exception as e:
        st.error(f"Error fetching {url}: {e}")
    return list_links

def get_job_details(job_url):
    description = ""
    posting_age = ""
    try:
        response = requests.get(job_url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(response.text, 'html.parser')
        script_tag = soup.find('script', type='application/ld+json')
        if script_tag:
            data = json.loads(script_tag.string)
            description = data.get('description', '').strip()
            date_posted = data.get('datePosted', '')
            if date_posted:
                date_posted = date_posted.split('T')[0]  # Remove time component
                posted_date = datetime.strptime(date_posted, '%Y-%m-%d')
                posting_age = f"{(datetime.now() - posted_date).days} days ago"
    except Exception:
        pass  # Silently skip failed descriptions
    return description, posting_age

def save_csv(df, name):
    name = name.replace("\n", '').strip().replace(" ", "_")
    filepath = f"{name}.csv"
    df.to_csv(filepath, index=False)
    st.success(f"Saved CSV as {filepath}")

def open_all_links(df):
    for url in df["Link"].to_numpy():
        webbrowser.open_new_tab(url)

def analyze_descriptions(descriptions, user_keywords):
    stop_words = set(stopwords.words('english'))
    all_words = re.findall(r'\b\w+\b', ' '.join(descriptions).lower())
    filtered_words = [word for word in all_words if word not in stop_words and len(word) > 2]
    common_words = Counter(filtered_words).most_common(10)

    keyword_freq = {kw: 0 for kw in user_keywords}
    for word in all_words:
        if word in keyword_freq:
            keyword_freq[word] += 1

    st.subheader("🔍 Keyword Analysis")
    st.write("**Most common overlapping words in job descriptions (excluding stopwords):**")
    for word, freq in common_words:
        st.write(f"- {word}: {freq} times")

    st.write("\n**Frequency of your searched keywords in job descriptions:**")
    for kw, freq in keyword_freq.items():
        st.write(f"- {kw}: {freq} times")

    # WordCloud
    st.write("\n**Word Cloud:**")
    wordcloud = WordCloud(width=800, height=400, background_color='white').generate(' '.join(filtered_words))
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.imshow(wordcloud, interpolation='bilinear')
    ax.axis('off')
    st.pyplot(fig)

# ---------- Main App ----------
def main():
    st.set_page_config(page_title="LinkedIn Job Scraper with Graph", layout="wide")
    st.title("LinkedIn Job Scraper + Network Graph")

    SearchQueryVal = st.text_input("Enter Search Query:", "")
    if not SearchQueryVal:
        st.stop()

    default_keyword_value = ",".join(SearchQueryVal.split())
    keyword_input = st.text_input("Enter Keywords (comma-separated):", value=default_keyword_value)
    keywords = [kw.strip().lower() for kw in keyword_input.split(',') if kw.strip()]

    depth = st.slider("Select Tree Depth (Exponential):", 1, 4, 2)

    if st.button("Start Scraping"):
        formatted_query = format_search_query(SearchQueryVal)
        ROOT = [f"https://www.linkedin.com/jobs/search/?keywords={formatted_query}&location=India&origin=JOB_SEARCH_PAGE_SEARCH_BUTTON"]
        all_links = []
        edges = []
        seen_urls = set()

        scroll_container = st.empty()
        scroll_html = ""

        st.info("Scraping in progress...")
        progress = st.progress(0)

        for d in range(depth):
            new_root = []
            for i, url in enumerate(ROOT):
                links = get_links_from_body(url)
                for link, title in links:
                    if 'linkedin.com/jobs/view' in link and any(k in link.lower() for k in keywords):
                        clean_url = link.split('?')[0]
                        if clean_url not in seen_urls:
                            seen_urls.add(clean_url)
                            description, age = get_job_details(clean_url)
                            cropped_desc = (description[:100] + '...') if len(description) > 100 else description
                            all_links.append((f'<a href="{clean_url}" target="_blank">{title.strip()}</a>', clean_url, cropped_desc, age))
                            edges.append((url, clean_url))
                            scroll_html += f'<a href="{clean_url}" target="_blank">{title.strip()}</a><br>'
                            styled_html = f"""
                            <div style='height:300px; overflow-y:auto; padding:10px; border:1px solid #ccc; background:#f9f9f9;'>
                                {scroll_html}
                            </div>
                            """
                            scroll_container.markdown(styled_html, unsafe_allow_html=True)
                        new_root.append(clean_url)
                progress.progress((d + 1) / depth)
            ROOT = new_root

        df = pd.DataFrame(all_links, columns=["Title", "Link", "Description", "Posting Age"])

        st.subheader("Results")
        st.write("Clickable job titles with links:")
        st.write(df.to_html(escape=False, index=False), unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Save to CSV"):
                save_csv(df, SearchQueryVal)
        with col2:
            if st.button("Open All Links"):
                open_all_links(df)

        st.subheader("Job Network Graph")
        G = nx.DiGraph()
        for src, tgt in edges:
            G.add_edge(src, tgt)

        net = Network(height='600px', width='100%', directed=True)
        net.from_nx(G)
        net.show_buttons(filter_=['physics'])
        net.save_graph('job_graph.html')
        with open("job_graph.html", "r", encoding="utf-8") as f:
            graph_html = f.read()
        components.html(graph_html, height=600, scrolling=True)

        # Run analysis on descriptions
        analyze_descriptions(df['Description'].tolist(), keywords)

if __name__ == "__main__":
    main()
