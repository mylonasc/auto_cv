import asyncio
import os
import sys
import pytest
from pathlib import Path

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils import JobPostAnalysis, FullCVDocument, DocSection, DocSectionItem
from src.utils_cross_analysis import CVCrossAnalyzer

@pytest.mark.asyncio
async def test_cv_cross_analysis():
    # 1. Setup Job Post
    """Test cv cross analysis.

    Returns:
        TODO: describe return value.
    """
    job_post_content = """
    We are looking for a Senior Software Engineer at TechCorp.
    Requirements:
    - 5 years of Python experience
    - Experience with LLMs and LangChain
    - Ph.D. in Computer Science preferred
    """
    with open('test_job_post_cross.txt', 'w') as f:
        f.write(job_post_content)
        
    # 2. Setup CV
    doc_item = DocSectionItem(
        company="OldCorp",
        duration="2018-2023",
        position="Software Engineer",
        text_items=[
            "Developed Python applications using LangChain.",
            "Implemented deep learning models."
        ]
    )
    doc_section = DocSection("Work Experience", [doc_item])
    fcv = FullCVDocument("I am an experienced engineer with a PhD.", doc_section)
    
    try:
        jpa = JobPostAnalysis('test_job_post_cross.txt')
        await jpa.analyze()
        
        cvca = CVCrossAnalyzer(jpa, fcv)
        
        # Test personal statement analysis
        await cvca.analyze_personal_statement()
        assert 'personal_statement_analysis' in cvca.data
        assert 'experience_relevance_score' in cvca.data['personal_statement_analysis']
        
        # Test experience section analysis (parallel fan-out)
        await cvca.analyze_job_experience_section()
        assert 'experience_section_analysis' in cvca.data
        
        analysis = cvca.data['experience_section_analysis']
        assert 'full_section_analysis' in analysis
        assert 'by_section_item_analysis' in analysis
        
        # Check that we have results for the section
        assert len(analysis['full_section_analysis']) > 0
        
        print("CVCrossAnalyzer test passed!")
        
    finally:
        if os.path.exists('test_job_post_cross.txt'):
            os.remove('test_job_post_cross.txt')

if __name__ == "__main__":
    asyncio.run(test_cv_cross_analysis())
