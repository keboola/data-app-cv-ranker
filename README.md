# data-app-cv-ranker
A plug-and-play application takes uploads job descriptions and candidates from the Lever component and lets the user choose the position he wants to analyze  
The app analyzes the CVs using openAI and outputs ranked results by how much each candidate fits the job description.

Requirements:
- All CVs have to be RTFs

The app is built to use the Lever component tables. 
Specifically:  
- opportunities
- applications
- postings
- resumes

Secrets used:  
openai_token - OpenAI API token (with access to the model you would like to use), currently set up with gpt-3.5-turbo  
lever_token - Lever API token (to download the cvs)  
kbc_url - Keboola url  
kbc_token - Keboola token

| Version |    Date    |       Description        |
|---------|:----------:|:------------------------:|
| 1.0     | 2024-07-02 | A data app for CV Ranker |

