from backend.api.routes.admin import _role_value
from backend.models.user import UserRole


def test_role_value_handles_enum_and_legacy_strings():
    assert _role_value(UserRole.ADMIN) == "admin"
    assert _role_value(UserRole.USER) == "readonly"
    assert _role_value(UserRole.READONLY) == "readonly"
    assert _role_value("ANALYST") == "analyst"
    assert _role_value("analyst") == "analyst"
    assert _role_value("USER") == "readonly"
    assert _role_value("user") == "readonly"
    assert _role_value(None) == "readonly"
