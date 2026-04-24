from app.api.routes.admin import _role_value
from app.models.user import UserRole


def test_role_value_handles_enum_and_legacy_strings():
    assert _role_value(UserRole.OWNER) == "owner"
    assert _role_value(UserRole.ANALYST) == "analyst"
    assert _role_value(UserRole.VIEWER) == "viewer"
    assert _role_value("ANALYST") == "analyst"
    assert _role_value("analyst") == "analyst"
    assert _role_value("USER") == "analyst"
    assert _role_value("user") == "analyst"
    assert _role_value("admin") == "owner"
    assert _role_value(None) == "viewer"
