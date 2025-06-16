# auto_cv
The `auto_cv` project is a LLM ("GenAI")-enabled CV customizer. 

Given a job posting and a CV, the system creates a rendered file that
contains the parts of the experience of the CV candidate that are the most relevant and aligned with the provided posting. 

The system architecture diagram is as follows:

![high level system arhc](assets/images/auto_cv_v0-1.png)

## Enable Gemini 
For getting a Gemini API key one needs to 
1. Create a GCP project (if it does not exist already) [console.google.com](console.google.com)
2. Create an API key [here](https://aistudio.google.com/app/apikey)
