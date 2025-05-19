import streamlit as st
import requests
from bs4 import BeautifulSoup
import textwrap
import pandas as pd
import webbrowser

class WikiWebber:
    def wrap_text(self, input_text, width=10):
        return textwrap.fill(input_text, width)

    def get_links_from_body(self, url=None):
        list_links = []
        if not url:
            return list_links
        try:
            response = requests.get(url)
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

def vlink(link, keywords):
    return any(x in link for x in keywords)

def format_search_query(SQ):
    return SQ.replace(" ", "%20")

def link_metadata_remover(link):
    return link.split('?')[0]

def check_keywords(keywords, val):
    return any(x in val.lower() for x in keywords)

def save_csv(df, name):
    name = name.replace('\n', '').strip().replace(" ", "_")
    filepath = f"{name}.csv"
    df.to_csv(filepath, index=False)
    st.success(f"Saved CSV as {filepath}")

def open_all_links(df):
    for url in df["Link"].to_numpy():
        webbrowser.open_new_tab(url)

def main():
    st.set_page_config(page_title="LinkedIn Job Scraper", layout="wide")
    st.title("LinkedIn Job Scraper")

    SearchQueryVal = st.text_input("Enter Search Query:", "")
    if not SearchQueryVal:
        st.stop()

    default_keyword_value = ",".join(SearchQueryVal.split())
    keywords_input = st.text_input("Enter Keywords (comma separated):", value=default_keyword_value)
    keywords = [kw.strip().lower() for kw in keywords_input.split(',') if kw.strip()]

    depth = st.slider("Select Tree Depth (Exponential Complexity):", min_value=1, max_value=4, value=2)

    if st.button("Start Scraping"):
        W = WikiWebber()
        SearchQuery = format_search_query(SearchQueryVal)
        TRIES = 5
        current_try = 1
        all_links = []
        progress_text = st.empty()
        depth_bar = st.progress(0)

        # Scrollable container using HTML & Markdown
        scroll_container = st.empty()
        scroll_content = ""

        result_table = st.empty()

        with st.spinner("Scraping..."):
            while True:
                ROOT = [
                    f"https://www.linkedin.com/jobs/search/?keywords={SearchQuery}&location=India&origin=JOB_SEARCH_PAGE_SEARCH_BUTTON"
                ]
                v_links = []

                for depth_index in range(depth):
                    T_ROOT = []
                    progress_text.text(f"Depth {depth_index + 1}/{depth}")
                    for i, L in enumerate(ROOT):
                        links = W.get_links_from_body(L)
                        for x, h in links:
                            if (('linkedin.com/jobs/' in x) or ('in.linkedin.com/jobs/' in x)) and vlink(x, keywords):
                                T_ROOT.append(x)
                                if 'linkedin.com/jobs/view' in x:
                                    x = link_metadata_remover(x)
                                    if check_keywords(keywords, h):
                                        clean_heading = h.replace('\n', '').strip()
                                        v_links.append((x, clean_heading))

                                        # Append to scrollable section
                                        scroll_content += f'<a href="{x}" target="_blank">{clean_heading}</a><br>'
                                        styled_scroll = f"""
                                        <div style="height:300px; overflow-y:auto; padding:10px; border:1px solid #ccc; background:#f9f9f9;">
                                        {scroll_content}
                                        </div>
                                        """
                                        scroll_container.markdown(styled_scroll, unsafe_allow_html=True)

                        if len(ROOT) > 1:
                            percent_in_depth = (i + 1) / len(ROOT)
                            depth_bar.progress(min((depth_index + percent_in_depth) / depth, 1.0))

                    all_links += v_links
                    ROOT = T_ROOT

                if all_links or current_try == TRIES:
                    break
                current_try += 1

        if all_links:
            df = pd.DataFrame(all_links, columns=["Link", "Name"])
            df = df.drop_duplicates()
            df = df[["Name", "Link"]]  # reorder

            st.success(f"✅ Found {len(df)} job listings!")
            result_table.dataframe(df, use_container_width=True)

            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("Save to CSV"):
                    save_csv(df, SearchQueryVal)
            with col2:
                if st.button("Open All Links"):
                    open_all_links(df)
            with col3:
                st.button("New Search", on_click=lambda: st.experimental_rerun())
        else:
            st.warning("No valid job links found.")

if __name__ == "__main__":
    main()
