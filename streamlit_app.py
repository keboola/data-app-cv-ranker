import json
import pandas as pd
import streamlit as st
import PyPDF2
import random
from openai import OpenAI
import streamlit.components.v1 as components
import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from io import BytesIO
from kbcstorage.client import Client
import csv
import requests
from striprtf.striprtf import rtf_to_text


openai_token = st.secrets["openai_token"]
lever_token = st.secrets["lever_token"]
kbc_url = st.secrets["kbc_url"]
kbc_token = st.secrets["kbc_token"]
lever_bucket = st.secrets["lever_bucket"]

client = Client(kbc_url, kbc_token)
LOGO_IMAGE_PATH = os.path.abspath("./app/static/keboola.png")

# Setting page config
st.set_page_config(page_title="Keboola Resume Analyzer", layout="wide")


@st.cache_data(ttl=60, show_spinner=False)
def hide_custom_anchor_link():
    st.markdown(
        """
        <style>
            /* Hide anchors directly inside custom HTML headers */
            h1 > a, h2 > a, h3 > a, h4 > a, h5 > a, h6 > a {
                display: none !important;
            }
            /* If the above doesn't work, it may be necessary to target by attribute if Streamlit adds them dynamically */
            [data-testid="stMarkdown"] h1 a, [data-testid="stMarkdown"] h3 a,[data-testid="stMarkdown"] h5 a,[data-testid="stMarkdown"] h2 a {
                display: none !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=60, show_spinner=False)
def display_footer_section():
    # Inject custom CSS for alignment and style
    st.markdown(
        """
        <style>
            .footer {
                width: 100%;
                font-size: 14px;  /* Adjust font size as needed */
                color: #22252999;  /* Adjust text color as needed */
                padding: 10px 0;  /* Adjust padding as needed */
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .footer p {
                margin: 0;  /* Removes default margin for p elements */
                padding: 0;  /* Ensures no additional padding is applied */
            }
        </style>
        <div class="footer">
            <p>© Keboola 2024</p>
            <p>Version 1.0</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def ChangeButtonColour(widget_label, font_color, background_color, border_color):
    htmlstr = f"""
        <script>
            var elements = window.parent.document.querySelectorAll('button');
            for (var i = 0; i < elements.length; ++i) {{ 
                if (elements[i].innerText == '{widget_label}') {{ 
                    elements[i].style.color ='{font_color}';
                    elements[i].style.background = '{background_color}';
                    elements[i].style.borderColor = '{border_color}';
                }}
            }}
        </script>
        """
    components.html(f"{htmlstr}", height=0, width=0)


def get_openai_response(ai_setup, prompt, api_key):
    """
    Writes the provided data to the specified table in Keboola Connection,
    updating existing records as needed.

    Args:
        ai_setup (str): The instructions to send to OpenAI. In case of a conversation this is instructions for the system.
        prompt (str): In case of a conversation this is instructions for the user.
        api_key (str): OpenAI API key

    Returns:
        The text from the response from OpenAI
    """

    open_ai_client = OpenAI(
        api_key=api_key,
    )
    random.seed(42)
    messages = [{"role": "system", "content": ai_setup}]
    if prompt:
        messages.append({"role": "user", "content": prompt})

    try:
        completion = open_ai_client.chat.completions.create(
            model="gpt-3.5-turbo", messages=messages, temperature=0
        )

        message = completion.choices[0].message.content

        # Extracting the text response from the response object
        return message

    except Exception as e:
        return f"An error occurred: {e}"


def get_dataframe(table_name):
    """
    Reads the provided table from the specified table in Keboola Connection.

    Args:
        table_name (str): The name of the table to write the data to.

    Returns:
        The table as dataframe
    """
    table_detail = client.tables.detail(table_name)
    client.tables.export_to_file(table_id=table_name, path_name="")
    list = client.tables.list()
    with open("./" + table_detail["name"], mode="rt", encoding="utf-8") as in_file:
        lazy_lines = (line.replace("\0", "") for line in in_file)
        reader = csv.reader(lazy_lines, lineterminator="\n")
    if os.path.exists("data.csv"):
        os.remove("data.csv")
    else:
        print("The file does not exist")
    os.rename(table_detail["name"], "data.csv")
    data = pd.read_csv("data.csv")
    return data


def read_pdf(file):
    # Function to read a PDF file and return its text
    pdf_reader = PyPDF2.PdfReader(file)
    num_pages = len(pdf_reader.pages)
    text = ""
    for page_num in range(num_pages):
        text += pdf_reader.pages[page_num].extract_text()
    return text


def analyze_cv(cv_text, job_description):
    ai_setup = """
            You are an assistant tasked with evaluating whether a CV matches a job description. Your output should be formatted as a JSON object in the following structure:
            {
                "name": "extract the name of the candidate from the cv",
                "summary": "summary of the candidate's CV",
                "score": Provide a score between 0.0 to 100.0 that represents the percentage of job description requirements met by the candidate's CV,
                "fit": "Describe whether the candidate fits the job description or not. Provide an explanation why",
                "speculation": "Describe whether you think the candidate can succeed in the job taking in mind your answer for whether they fit or not",
            }
            Follow the format strictly.
            Ensure your evaluation is objective, thorough, and based solely on the information provided in the CV and job description.
            """ + f"\n\nJob Description: {job_description}" + f"\n\nCV: {cv_text}"
    for j in range(3):
        # Retries up to 3 times if the returned json is broken. If on the 3rd time it is broken returns none
        try:
            res = get_openai_response(ai_setup, None, openai_token)
            return json.loads(res)
        except json.JSONDecodeError:
            continue
    return None


def get_candidate_scores(candidates_for_scoring):
    ai_setup = ("""Score each candidate on a scale of 0.0 to 100.0 based on the sentiment score from the reason, their fit to the requirements and relative to each other. 
                    The input will be provided with the following fields:
                        file_name: name of the file
                        requirement_score: a score that represents the percentage of the requirements the candidate fullfills
                        reason: summary of the candidate's cv regarding the job description
                    
                    Provide the scores in a JSON format with 'file_name' as key and the score as value.
            
                    Instructions:
                        Take in account all the data you are given
                        Make sure all the candidates are scored exactly once
                        Ensure scores are varied and accurately reflect the differences in candidates’ qualifications and experiences. Avoid giving the same score to different candidates unless their qualifications are truly identical.
              """ + f"\n\nCandidates:\n{candidates_for_scoring.to_string(index=False)}")
    res_json = None
    for j in range(2):
        # Retries up to 2 times if the not all the keys are in the results. After that returns result as is
        res = get_openai_response(ai_setup, None, openai_token)
        res_json = json.loads(res)
        if len(res_json.keys()) == candidates_for_scoring.shape[0]:
            return res_json
    return res_json


def create_pdf(pdf_text):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    lines = pdf_text.split('\n')
    for line in lines:
        paragraph = Paragraph(line, styles['Normal'])
        story.append(paragraph)
        story.append(Spacer(1, 12))

    doc.build(story)
    buffer.seek(0)
    return buffer


def download_and_extract_rtf(url):
    headers = {
        'authorization': lever_token
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        rtf_content = response.text
        return rtf_to_text(rtf_content)
    else:
        print(f"Failed to download the file. Status code: {response.status_code}")
        return None


def prepare_data():
    opportunities = get_dataframe(lever_bucket + '.opportunities')
    opportunities = opportunities[['id', 'name', 'urls_show']]
    applications = get_dataframe(lever_bucket + '.applications')
    applications = applications[['posting', 'opportunityId']]
    postings = get_dataframe(lever_bucket + '.postings')
    postings = postings[['id', 'content_description', 'state', 'text', 'urls_show']]
    postings = postings[postings['state'] != 'closed']
    resumes = get_dataframe(lever_bucket + '.resumes')
    resumes = resumes[['opportunity_id', 'file_downloadUrl', 'file_name']]
    cvs = pd.merge(postings, applications, how='left', left_on=['id'], right_on=['posting'])
    postings = cvs[cvs['posting'].notnull()][['id', 'content_description', 'state', 'text', 'urls_show']].copy()
    postings.drop_duplicates(inplace=True, ignore_index=True)
    cvs = pd.merge(cvs, opportunities, how='left', left_on=['opportunityId'], right_on=['id'])
    cvs = pd.merge(cvs, resumes, how='left', left_on=['opportunityId'], right_on=['opportunity_id'])
    cvs = cvs[cvs['opportunity_id'].notnull()]
    st.session_state.cvs = cvs
    st.session_state.postings = postings


# Streamlit app
st.image(LOGO_IMAGE_PATH)
hide_img_fs = """
        <style>
        button[title="View fullscreen"]{
            visibility: hidden;}
        </style>
        """
st.markdown(hide_img_fs, unsafe_allow_html=True)

st.markdown("""
<style>
.big-font {
    font-size:42px !important;
    font-weight: bold !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown(
    '<div class="big-font"><span style="color:#1f8fff;">Keboola</span> Resume Analyzer</div>',
    unsafe_allow_html=True)


if "cvs" not in st.session_state:
    prepare_data()
cvs = st.session_state.cvs
postings = st.session_state.postings
button_style = """
    <style>
    .stButton > button {
        width: 100%;
        border-radius: 10px;
    }
    </style>
    """


back_container = st.container()
back_container.markdown(button_style, unsafe_allow_html=True)
settings_container = st.container()
reviews_container = st.container()
candidates = {}
errors = []


if "screen" not in st.session_state:
    st.session_state.screen = 'settings'
screen = st.session_state.screen
if screen == 'settings':
    settings_container.info(
        "The Keboola AI-Powered Resume Matching Automation Template gathers open positions from your LEVER (other HRIS with API are coming), processes all applications for each job opening, and provides a sorted list of resumes with a match quality score and reasoning for this score. Access to the application and data is restricted to authorized HR personnel, ensuring required privacy and security. The final hiring decision remains with the HR team, supported by Gen AI insights.",
        icon="ℹ️"
    )
    job_posting = settings_container.selectbox("Select a Vacancy", postings['text'].to_list())
    posting_url = postings[postings['text'] == job_posting]['urls_show']
    settings_container.selectbox("Vacancy Link", posting_url.to_list(), disabled=True)
    st.session_state.applicants = cvs[cvs['text'] == job_posting].reset_index(drop=True)
    st.session_state.job_description = postings[postings['text'] == job_posting]['content_description']
    settings_container.success(f"Found {len(st.session_state.applicants)} resumes that meet your requirements", icon="✅")
    loading_container = settings_container.container()
    if "cvs" in st.session_state:
        container = settings_container.container()
        with container:
            col1, col2, col3 = st.columns([3, 2, 3])
            # Place the button in the center column
            with col2:
                analyze_button = st.button("Analyze Resumes")

        ChangeButtonColour("Analyze Resumes", "#FFFFFF", "#1EC71E", "#1EC71E")

    if analyze_button:
        st.session_state.screen = 'cvs'
        progress_bar = loading_container.progress(0)
        status_text = loading_container.text('Analyzing... 0% Done')
        applicants = st.session_state.applicants
        job_description = st.session_state.job_description
        for index, row in applicants.iterrows():
            cv_text = download_and_extract_rtf(row['file_downloadUrl'])
            cv_analysis = analyze_cv(cv_text, job_description)
            if cv_analysis is None or cv_text is None:
                errors.append(row['name'])
                continue
            candidates[row['file_name']] = {
                'file_name': row['file_name'],
                'url': row['urls_show_y'],
                'cv_text': cv_text,
                'name': row['name'],
                'summary': cv_analysis['summary'],
                'requirement_score': cv_analysis['score'],
                "fit": cv_analysis['fit'],
                "speculation": cv_analysis['speculation'],
            }
            progress_bar.progress((index + 1) / len(applicants))
            status_text.text(f"Analyzing... {round((index + 1) / len(applicants) * 100, 1)}% Done")
        df = pd.DataFrame.from_dict(candidates, orient='index')
        df['reason'] = df['fit'] + df['speculation']
        status_text.text('Scoring CVs...')
        scores = get_candidate_scores(df[['file_name', 'reason', 'requirement_score']])
        for c in candidates.keys():
            if c in scores.keys():
                candidates[c]['score'] = scores[c]
            else:
                candidates[c]['score'] = -1

        st.session_state['sorted_candidates'] = dict(
            sorted(candidates.items(), key=lambda x: (x[1]['score']), reverse=True))
        st.session_state['errors'] = errors
        progress_bar.empty()
        status_text.empty()
        st.rerun()

if screen == 'cvs':
    applicants = st.session_state.applicants
    job_description = st.session_state.job_description
    if back_container.button("← BACK TO SETTINGS", key='back_to_settings'):
        st.session_state.screen = 'settings'
        st.rerun()
    st.write("Candidates")
    st.info(
        "The matching score, ranging from 0 to 100, is an AI-generated metric that evaluates how well a candidate fits the job opening. It considers various factors from the candidate's application. Detailed reasoning for the score is provided.",
        icon="ℹ️"
    )
    if "sorted_candidates" in st.session_state:
        sorted_candidates = st.session_state['sorted_candidates']
        errors = st.session_state['errors']
        text = f"Analyzed {len(sorted_candidates)}/{len(applicants)} CV files. "
        st.text(text)
        if errors:
            st.text("See files that couldn't be processed at the bottom of the page.")

        for cv in sorted_candidates.keys():
            score_to_show = sorted_candidates[cv]['score'] if sorted_candidates[cv]['score'] != -1 else 'N/A'
            expander_label = f"""
            <div>
                <details>
                    <summary style='display: flex; align-items: center;'>
                        <div style='display: flex; align-items: center;'>
                            <div style='margin:0px 0px; background-color: #82d582; border-radius: 5px; padding: 10px 15px; font-size: 24px; font-weight: bold; color: white;'>
                                {score_to_show}
                            </div>
                            <div style='margin-left: 15px;'>
                                <p style='margin: 0; padding: 0; font-weight: bold; font-size: 24px;'>{sorted_candidates[cv]['name']}</p>
                                <a href='{sorted_candidates[cv]['url']}' style='font-size: 14px; color: #2196F3;'>Open in Lever</a>
                            </div>
                        </div>
                        <span style="font-size: 18px; margin-left: auto; float: right;">&#9662;</span>
                    </summary>
                    <div>
                        <div>
                            <p style='margin: 0; padding: 0; font-weight: bold; font-size: 18px;'>Candidate's fit</p>
                            {sorted_candidates[cv]['fit']}
                            <br>
                            {sorted_candidates[cv]['speculation']}
                        </div>
                        <div>
                            <p style='margin: 0; padding: 0; font-weight: bold; font-size: 18px;'>CV Summary</p>
                            {sorted_candidates[cv]['summary']}
                        </div>
                    </div>
                </details>
            </div>
            """
            #
            with st.container(border=True):
                st.markdown(expander_label, unsafe_allow_html=True)
                st.markdown("""
                                <style>
                                    details > summary {
                                        list-style: none;
                                    }
                                </style>
                                """, unsafe_allow_html=True)

    if errors:
        st.write('Unable to process the following files')
        st.write(', '.join(map(str, errors)))

display_footer_section()
