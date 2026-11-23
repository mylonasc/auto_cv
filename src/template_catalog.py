"""TRF-02 / RFK-04: injected managed revision lookup, never mutable HEAD rendering."""

from pathlib import Path

from .paths import data_root
from .template_storage import ManagedTemplateRepository
from .template_registry import TemplateError


class TemplateCatalog:
    def __init__(self, directory: Path):
        self.repository = ManagedTemplateRepository(directory)

    @classmethod
    def from_env(cls):
        return cls(data_root() / 'template_packages')

    def get(self, reference):
        if reference.revision is None:
            raise TemplateError('Managed rendering requires an explicit revision')
        try:
            return self.repository.get(reference.template_id, reference.revision).package
        except (FileNotFoundError, ValueError) as error:
            raise TemplateError(f'Cannot load managed template {reference.template_id}@{reference.revision}: {error}') from error
