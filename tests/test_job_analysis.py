import asyncio
import os
import sys
import pytest
from pathlib import Path

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils import JobPostAnalysis


def test_postprocess_analysis_replaces_placeholders(tmp_path: Path):
    """Replace placeholder basic analysis values with extracted content."""
    job_post_content = """
    Senior ML Engineer
    Requirements:
    - 5+ years of Python experience
    - Experience with LLMs and RAG systems
    - Strong communication skills
    Qualifications:
    - MS or PhD in Computer Science or equivalent experience
    """

    job_post_file = tmp_path / "job_post.txt"
    job_post_file.write_text(job_post_content, encoding="utf-8")

    jpa = JobPostAnalysis(str(job_post_file), llm_model=None)
    jpa.data = {
        "basic_analysis": {
            "skills": "required skills",
            "qualifications": "required qualifications",
            "preferred_qualifications": "none",
        }
    }

    jpa._postprocess_analysis()

    basic = jpa.data["basic_analysis"]
    assert basic["skills"].lower() != "required skills"
    assert basic["qualifications"].lower() != "required qualifications"
    assert isinstance(basic["skills"], str) and len(basic["skills"].strip()) > 0
    assert isinstance(basic["qualifications"], str) and len(basic["qualifications"].strip()) > 0
    assert basic["preferred_qualifications"] is None

@pytest.mark.asyncio
async def test_job_post_analysis():
    # Create a dummy job post file
    """Test job post analysis.

    Returns:
        TODO: describe return value.
    """
    job_post_content = """
    We are looking for a Senior Software Engineer at TechCorp.
    Requirements:
    - 5 years of Python experience
    - Experience with LLMs and LangChain
    - Ph.D. in Computer Science preferred
    - Industry: AI and Software Development
    """
    
    with open('test_job_post.txt', 'w') as f:
        f.write(job_post_content)
        
    try:
        jpa = JobPostAnalysis('test_job_post.txt')
        await jpa.analyze()
        
        # Verify data structure
        assert 'basic_analysis' in jpa.data
        assert 'industry_and_position_analysis' in jpa.data
        
        basic = jpa.data['basic_analysis']
        assert 'skills' in basic
        assert 'qualifications' in basic
        
        ind_pos = jpa.data['industry_and_position_analysis']
        assert 'company_name' in ind_pos
        assert 'job_title' in ind_pos
        
        print("JobPostAnalysis test passed!")
        print("Data:", jpa.data)
        
    finally:
        if os.path.exists('test_job_post.txt'):
            os.remove('test_job_post.txt')

if __name__ == "__main__":
    asyncio.run(test_job_post_analysis())
