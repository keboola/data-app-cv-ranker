# data-app-cv-ranker
A plug-and-play application takes up to 70 CV pdf files and a job description (as a pdf or free text).  
The app analyzes the CVs using openAI and outputs ranked results by how much each candidate fits the job description.

Requirements:
- All CVs have to be pdfs
- Job description is either text or PDF

The app is built to support the Shopify component. 
If the data should come from different component, either:
- Transform the table to have the requirements
- Add code for handling the new component in the load_data() function

Secrets used:
openai_token - OpenAI API token (with access to the model you would like to use), currently set up with gpt-3.5-turbo  

| Version |    Date    |       Description        |
|---------|:----------:|:------------------------:|
| 1.0     | 2024-07-02 | A data app for CV Ranker |

