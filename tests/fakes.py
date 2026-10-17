"""Deterministic external dependencies; application chains remain real."""

from dataclasses import dataclass
from pathlib import Path

from langchain_core.runnables import RunnableLambda


class StructuredModel:
    """Answer the actual structured-output chains without a provider SDK."""

    def __init__(self):
        self.calls = []

    def __call__(self, prompt):
        self.calls.append(("CoverLetter", prompt.to_string()))
        return "<COVERLETTER>I bring Python delivery experience.</COVERLETTER>"

    def with_structured_output(self, schema):
        def respond(prompt):
            text = prompt.to_string()
            self.calls.append((schema.__name__, text))
            answers = {
                "BasicAnalysis": {
                    "skills": "Python; LangChain",
                    "qualifications": "5 years of Python experience",
                    "preferred_qualifications": "Ph.D. in Computer Science",
                },
                "IndustryPositionAnalysis": {
                    "company_name": "TechCorp",
                    "industry": "Software",
                    "job_title": "Senior Software Engineer",
                    "business_skills": 3,
                    "hands_on_skills": 9,
                },
                "BulletAnalysis": {
                    "experience_relevance_score": 2 if "admin" in text.lower() else 9,
                    "explanation": "Deterministic bullet assessment",
                    "posting_evidence": "Python experience",
                },
                "SectionAnalysis": {
                    "experience_relevance_score": 8,
                    "explanation": "Deterministic role assessment",
                    "posting_evidence": "Software delivery",
                },
                "PersonalStatementAnalysis": {
                    "experience_relevance_score": 8,
                    "explanation": "Relevant engineering experience",
                },
                "PersonalStatementRewrite": {
                    "edited_statement": "Experienced Python engineer.",
                    "analysis": "Selected supplied engineering experience",
                },
            }
            # Unknown schemas fail loudly instead of returning plausible empty data.
            return schema(**answers[schema.__name__])

        return RunnableLambda(respond)


@dataclass
class PDFCall:
    latex: str
    output: Path
