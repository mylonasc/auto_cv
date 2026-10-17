import pytest

from src.utils import JobPostAnalysis, FullCVDocument, DocSection, DocSectionItem
from src.utils_cross_analysis import CVCrossAnalyzer


@pytest.mark.asyncio
async def test_cv_cross_analysis(tmp_path, fake_model):
    posting = tmp_path / "job.txt"
    posting.write_text("TechCorp needs Python and LangChain experience.")
    role = DocSectionItem("OldCorp", "2018-2023", "Engineer", [
        "Developed Python applications using LangChain.", "Did admin work.",
    ])
    document = FullCVDocument("Experienced engineer.", DocSection("Work Experience", [role]))
    analyzer = JobPostAnalysis(str(posting), llm_model=fake_model)
    await analyzer.analyze()
    cross = CVCrossAnalyzer(analyzer, document, llm_model=fake_model)
    await cross.analyze_personal_statement()
    assert cross.data["personal_statement_analysis"]["experience_relevance_score"] == 8

    progress = []

    async def record(message):
        progress.append(message)

    result = await cross.analyze_job_experience_section(progress_callback=record)
    assert result["full_section_analysis"][role]["experience_relevance_score"] == 8
    bullets = result["by_section_item_analysis"][role]
    assert [bullets[bullet]["experience_relevance_score"] for bullet in role.section_item_list] == [9, 2]
    assert len(progress) == 3
    cross.rewrite_reviewed_experience_section(min_relevance_score=5)
    assert [bullet.text for bullet in role.section_item_list] == [
        "Developed Python applications using LangChain.",
    ]
