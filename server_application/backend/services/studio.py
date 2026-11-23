"""TRF-03: authoring operations over injected immutable template storage."""

from src.paths import project_root
from src.template_import import BUILTINS, import_builtin_template
from src.template_registry import TemplateError
from ..models.studio import StudioDraft


class StudioService:
    def __init__(self, repository):
        self.repository = repository
        self.root = project_root()

    def import_draft(self, request):
        cv = request.cv
        if request.source_template is not None:
            if cv.document is not None or cv.cv_template.revision is not None:
                raise TemplateError('A composed CV already owns its template; clone its managed package instead of importing a starter')
            if request.source_template not in BUILTINS:
                raise TemplateError(f'Unknown starter template: {request.source_template!r}')
            cv = cv.model_copy(deep=True)
            cv.cv_template.template_id = request.source_template
            cv.cv_template.template_path = None
        draft = import_builtin_template(cv, root=self.root,
            new_template_id=request.template_id, name=request.name)
        return StudioDraft(cv=draft.cv, package=draft.package)

    def save(self, request):
        return self.repository.save(request.package, expected_revision=request.expected_revision)
