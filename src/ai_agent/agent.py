from .permissions import can_modify


class RahYarAgent:
    """Safe foundation for future autonomous development workflows."""

    def analyze(self):
        return {
            "project": "RahYar Academy Management System",
            "framework": "aiogram",
            "database": "SQLAlchemy",
            "status": "ready",
        }

    def check_permission(self, path: str):
        return can_modify(path)
