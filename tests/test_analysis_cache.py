"""Cache entries must mean the same effective analysis, not merely the same text."""

import json
from types import SimpleNamespace

import pytest

from src.utils import FullCVDocument, DocSection, DocSectionItem
from src.utils_cross_analysis import AnalysisResultCache, CVCrossAnalyzer


@pytest.mark.asyncio
async def test_identical_effective_analysis_reuses_cache_but_changed_inputs_do_not(tmp_path, fake_model, monkeypatch):
    import src.utils_cross_analysis as module
    cache = AnalysisResultCache(str(tmp_path / 'cache.json'))

    async def analyze(*, text='Python delivery', posting='Python required', skills='Python',
                      company='Example', provider='ollama', model='one', temperature=0):
        posting = SimpleNamespace(post_txt=posting, data={'basic_analysis': {'skills': skills}})
        document = FullCVDocument('Statement', DocSection('Experience', [
            DocSectionItem(company, '2020', 'Engineer', [text]),
        ]))
        analyzer = CVCrossAnalyzer(posting, document, llm_model=fake_model, cache=cache,
            model_identity={'provider': provider, 'model': model, 'config': {'temperature': temperature}})
        await analyzer.analyze_job_experience_section()
        return analyzer

    initial = await analyze()
    assert len(fake_model.calls) == 2
    # Different transient content IDs do not invalidate otherwise identical work.
    second = await analyze()
    assert len(fake_model.calls) == 2
    assert initial.snapshot.roles[0].items[0].assessment == second.snapshot.roles[0].items[0].assessment
    for change in ({'text': 'Different delivery'}, {'posting': 'Different posting'}, {'skills': 'SQL'},
                   {'provider': 'google'}, {'model': 'two'}, {'temperature': .5}):
        count = len(fake_model.calls)
        await analyze(**change)
        assert len(fake_model.calls) == count + 2, change
    # Role context affects synthesis, not independent bullet analysis.
    count = len(fake_model.calls)
    await analyze(company='Other')
    assert len(fake_model.calls) == count + 1
    count = len(fake_model.calls)
    monkeypatch.setattr(module, 'section_experience_analysis_prompt', module.section_experience_analysis_prompt + '\nVersion 2')
    await analyze()
    assert len(fake_model.calls) == count + 1
    count = len(fake_model.calls)
    schema = module.BulletAnalysis.model_json_schema()
    monkeypatch.setattr(module.BulletAnalysis, 'model_json_schema', classmethod(lambda cls: {**schema, 'version': 'next'}))
    await analyze()
    assert len(fake_model.calls) == count + 1
    count = len(fake_model.calls)
    monkeypatch.setattr(module, 'CACHE_FORMAT', 3)
    await analyze()
    assert len(fake_model.calls) == count + 2


@pytest.mark.parametrize('original', [b'invalid JSON', b'{"old-key": {"score": 9}}', b'[]'])
def test_corrupt_and_legacy_caches_are_misses_and_never_overwritten(tmp_path, original):
    path = tmp_path / 'cache.json'
    path.write_bytes(original)
    cache = AnalysisResultCache(str(path))
    assert cache.get('old-key') is None
    cache.set('new-key', {'experience_relevance_score': 9, 'explanation': 'valid', 'posting_evidence': 'posting'})
    assert cache.get('new-key')['experience_relevance_score'] == 9
    assert cache.warnings
    assert path.read_bytes() == original


def test_invalid_v2_assessment_is_a_warned_miss(tmp_path):
    path = tmp_path / 'cache.json'
    path.write_text(json.dumps({'format': 2, 'entries': {'key': {'experience_relevance_score': 99}}}))
    cache = AnalysisResultCache(str(path))
    assert cache.get('key') is None
    assert cache.warnings


def test_cache_write_failure_is_visible_but_not_analysis_failure(tmp_path, monkeypatch):
    import src.utils_cross_analysis as module
    cache = AnalysisResultCache(str(tmp_path / 'cache.json'))

    def fail(*args):
        raise OSError('disk failure')

    monkeypatch.setattr(module, 'atomic_write_json', fail)
    cache.set('key', {'experience_relevance_score': 9, 'explanation': 'valid', 'posting_evidence': 'posting'})
    assert cache.get('key')['experience_relevance_score'] == 9
    assert cache.warnings


def test_cache_validates_and_copies_values(tmp_path):
    cache = AnalysisResultCache(str(tmp_path / 'cache.json'))
    value = {'experience_relevance_score': 9, 'explanation': 'valid', 'posting_evidence': 'posting'}
    cache.set('key', value)
    value['explanation'] = 'mutated input'
    cache.get('key')['explanation'] = 'mutated read'
    assert cache.get('key')['explanation'] == 'valid'
    with pytest.raises(ValueError):
        cache.set('bad', {'experience_relevance_score': float('nan')})
    assert AnalysisResultCache(cache.cache_path).get('key')['explanation'] == 'valid'


@pytest.mark.asyncio
async def test_ad_hoc_models_without_identity_cannot_reuse_cache(tmp_path, fake_model):
    cache = AnalysisResultCache(str(tmp_path / 'cache.json'))
    for _ in range(2):
        analyzer = CVCrossAnalyzer(SimpleNamespace(post_txt='Posting', data={}),
            FullCVDocument('Statement', DocSection('Experience', [DocSectionItem('Example', '2020', 'Engineer', ['Python'])])),
            llm_model=fake_model, cache=cache)
        await analyzer.analyze_job_experience_section()
    assert len(fake_model.calls) == 4


def test_effective_model_identity_includes_endpoint_defaults_and_never_credentials(monkeypatch):
    from src.pipeline import cache_model_identity
    from src.config import BackendConfig
    config = BackendConfig()
    config.analysis_model.config = {'temperature': .5, 'API_KEY': 'secret'}
    model = SimpleNamespace(model='resolved:latest', temperature=.5)
    one = cache_model_identity(config, model)
    assert 'secret' not in json.dumps(one)
    assert one['resolved'] == {'model': 'resolved:latest', 'temperature': .5}
    monkeypatch.setenv('OLLAMA_HOST', 'http://other-server:11434')
    assert cache_model_identity(config, model) != one
