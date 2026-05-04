import asyncio
import os
import sys
import pytest
from pathlib import Path

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils import JobPostAnalysis

@pytest.mark.asyncio
async def test_job_post_analysis():
    # Create a dummy job post file
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
