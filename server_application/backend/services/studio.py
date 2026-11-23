"""TRF-03: authoring operations over injected immutable template storage."""

from src.paths import project_root
from src.template_import import import_builtin_template
from ..models.studio import StudioDraft


class StudioService:
    def __init__(self, repository):
        self.repository = repository
        self.root = project_root()

    def import_draft(self, request):
        draft = import_builtin_template(request.cv, root=self.root,
            new_template_id=request.template_id, name=request.name)
        return StudioDraft(cv=draft.cv, package=draft.package)

    def save(self, request):
        return self.repository.save(request.package, expected_revision=request.expected_revision)
