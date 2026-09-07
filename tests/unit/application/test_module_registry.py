from orchai.application.modules import FORGE, MODULE_REGISTRY, STUDIO, get_module, list_modules
from orchai.domain.identifiers import ModuleId


def test_forge_is_registered_with_the_full_workflow_pipeline() -> None:
    assert MODULE_REGISTRY[ModuleId("forge")] is FORGE
    assert FORGE.project_adapter_kind == "local_filesystem"
    assert FORGE.task_pipeline_mode == "full_workflow"
    assert FORGE.requires_project is True
    assert FORGE.default_role in FORGE.allowed_roles


def test_studio_is_registered_with_the_media_workspace_adapter() -> None:
    assert MODULE_REGISTRY[ModuleId("studio")] is STUDIO
    assert STUDIO.project_adapter_kind == "media_workspace"
    assert STUDIO.task_pipeline_mode == "conversational_with_protected_operations"
    assert STUDIO.requires_project is True
    assert STUDIO.default_role in STUDIO.allowed_roles


def test_list_modules_returns_every_registered_module() -> None:
    modules = list_modules()
    assert FORGE in modules
    assert STUDIO in modules
    assert len(modules) == len(MODULE_REGISTRY) == 2


def test_get_module_returns_none_for_an_unknown_id() -> None:
    assert get_module(ModuleId("does-not-exist")) is None
    assert get_module(ModuleId("forge")) is FORGE
    assert get_module(ModuleId("studio")) is STUDIO
