from src.utils import JobPostAnalysis
import pytest


def test_postprocess_analysis_replaces_placeholders(tmp_path, fake_model):
    posting = tmp_path / "job.txt"
    posting.write_text("Requirements:\n- Python and LLM delivery experience\n")
    analyzer = JobPostAnalysis(str(posting), llm_model=fake_model)
    analyzer.data = {"basic_analysis": {
        "skills": "required skills", "qualifications": "required qualifications",
        "preferred_qualifications": "none",
    }}
    analyzer._postprocess_analysis()
    basic = analyzer.data["basic_analysis"]
    assert "python" in basic["skills"].lower()
    assert "delivery experience" in basic["qualifications"]
    assert basic["preferred_qualifications"] is None


@pytest.mark.asyncio
async def test_job_post_analysis(tmp_path, fake_model):
    posting = tmp_path / "job.txt"
    posting.write_text("TechCorp needs a Senior Software Engineer with Python experience.")
    analyzer = JobPostAnalysis(str(posting), llm_model=fake_model)
    await analyzer.analyze()
    assert analyzer.data["basic_analysis"]["skills"] == "Python; LangChain"
    assert analyzer.data["industry_and_position_analysis"]["company_name"] == "TechCorp"
    assert {name for name, _ in fake_model.calls} == {
        "BasicAnalysis", "IndustryPositionAnalysis",
    }
    assert all(posting.read_text() in prompt for _, prompt in fake_model.calls)
