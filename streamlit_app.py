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

openai_token = st.secrets["openai_token"]
LOGO_IMAGE_PATH = os.path.abspath("./app/static/keboola.png")


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


# Streamlit app
st.image(LOGO_IMAGE_PATH)
hide_img_fs = """
        <style>
        button[title="View fullscreen"]{
            visibility: hidden;}
        </style>
        """
st.markdown(hide_img_fs, unsafe_allow_html=True)
title, download_all = st.columns([5, 1])
title.title("CV Analyzer")
with st.sidebar:
    # Upload CV files
    uploaded_cvs = st.file_uploader("Upload up to 70 CV PDF files", accept_multiple_files=True, type=["pdf"])
    jd_option = st.selectbox("Upload job description as", ["Free text", "PDF"])
    if jd_option == 'PDF':
        jd = st.file_uploader("Upload the CV template PDF file", type=["pdf"])
    else:
        jd = st.text_area("Job Description")


if st.sidebar.button("Analyze"):
    if uploaded_cvs and jd:
        progress_bar = st.progress(0)
        status_text = st.text('Analyzing... 0% Done')

        if jd_option == 'PDF':
            job_description = read_pdf(jd)
        else:
            job_description = jd
        candidates = {}
        errors = []
        for i, cv in enumerate(uploaded_cvs):
            cv_text = read_pdf(cv)
            cv_analysis = analyze_cv(cv_text, job_description)
            if cv_analysis is None:
                errors.append(cv.name)
                continue
            candidates[cv.name] = {
                'file_name': cv.name,
                'cv_file': cv,
                'cv_text': cv_text,
                'name': cv_analysis['name'],
                'summary': cv_analysis['summary'],
                'requirement_score': cv_analysis['score'],
                "fit": cv_analysis['fit'],
                "speculation": cv_analysis['speculation'],
            }

            progress_bar.progress((i+1)/len(uploaded_cvs))
            status_text.text(f"Analyzing... {round((i+1)/len(uploaded_cvs)*100, 1)}% Done")
        df = pd.DataFrame.from_dict(candidates, orient='index')
        df['reason'] = df['fit']+df['speculation']
        status_text = st.text('Scoring CVs...')
        scores = get_candidate_scores(df[['file_name', 'reason', 'requirement_score']])
        for c in candidates.keys():
            if c in scores.keys():
                candidates[c]['score'] = scores[c]
            else:
                candidates[c]['score'] = -1

        st.session_state['sorted_candidates'] = dict(sorted(candidates.items(), key=lambda x: (x[1]['score']), reverse=True))
        st.session_state['errors'] = errors
        progress_bar.empty()
        status_text.empty()
    else:
        st.error('Please upload all necessary files and provide a job description.', icon="🚨")
ChangeButtonColour("Analyze", "#FFFFFF", "#1EC71E", "#1EC71E")

if "sorted_candidates" in st.session_state:
    sorted_candidates = st.session_state['sorted_candidates']
    errors = st.session_state['errors']
    text = f"Analyzed {len(sorted_candidates)}/{len(uploaded_cvs)} CV files. "
    st.text(text)
    if errors:
        st.text("See files that couldn't be processed at the bottom of the page.")

    for cv in sorted_candidates.keys():
        score_to_show = sorted_candidates[cv]['score'] if sorted_candidates[cv]['score'] != -1 else 'N/A'
        with st.expander(f"{sorted_candidates[cv]['name']} - Score: {score_to_show}."):
            text_col, buttons_col = st.columns([3, 1])
            text_col.markdown(f"**Candidate's fit**")
            text_col.write(f"{sorted_candidates[cv]['fit']}")
            text_col.write(f"{sorted_candidates[cv]['speculation']}")
            text_col.markdown(f"**CV summary**")
            text_col.write(f"{sorted_candidates[cv]['summary']}")

            buttons_col.write(f"{cv}")
            buttons_col.download_button(
                label="Download Original CV",
                data=sorted_candidates[cv]['cv_file'],
                file_name=cv,
                mime="application/pdf"
            )
            ChangeButtonColour("Download Original CV", "#FFFFFF", "#1EC71E", "#1EC71E")

            summary_file_text = (f"{sorted_candidates[cv]['name']} - Overall score: {score_to_show}.\n\n"
                                 f"Candidate fit (requirements score: {sorted_candidates[cv]['requirement_score']}):\n"
                                 f"{sorted_candidates[cv]['fit']}\n{sorted_candidates[cv]['speculation']}\n\n"
                                 f"CV summary:\n{sorted_candidates[cv]['summary']}\n")
            buttons_col.download_button(
                label="Download Summary",
                data=create_pdf(summary_file_text),
                file_name='summary_' + cv,
                mime="application/pdf"
            )
            ChangeButtonColour("Download Summary", "#FFFFFF", "#1EC71E", "#1EC71E")
    df = pd.DataFrame.from_dict(sorted_candidates, orient='index')
    df = df[['file_name', 'name', 'summary', 'requirement_score', 'fit', 'speculation', 'score']]
    df['score'] = df['score'].apply(lambda x: 'N/A' if x == -1 else x)
    df.columns = ['Original CV file name', 'Candidate name', 'CV summary', 'Requirements score', 'Does the candidate fit the position?', 'Would the candidate succeed in the position', 'Final score']
    download_all.download_button(
        label="Download all as csv",
        data=df.to_csv(index=False).encode('utf-8'),
        file_name='cv_analysis.csv',
        mime="text/csv"
    )
    ChangeButtonColour("Download all as csv", "#FFFFFF", "#1EC71E", "#1EC71E")
    if errors:
        st.write('Unable to process the following files')
        st.write(', '.join(map(str, errors)))

    display_footer_section()

