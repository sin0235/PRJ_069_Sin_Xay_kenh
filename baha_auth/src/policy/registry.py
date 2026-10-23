# Danh mục quản lý 58 action key và 15 vai trò khởi tạo.
import os
import json
import csv
from typing import Dict, List, Optional, Set

REGISTRY_FILE = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..",
    "09_kiem_thu_quyen", "PERMISSION_REGISTRY.json"
))

_SCOPE_CODES = {
    "W": "WORKSPACE",
    "B": "BRAND",
    "D": "DEPARTMENT",
    "T": "TEAM",
    "P": "PROJECT",
    "H": "CHANNEL",
    "S": "OWN",
    "R": "CLIENT_REVIEWED",
    "A": "OBJECT",
    "O": "PLATFORM",
}

MATRIX_FILE = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..",
    "09_kiem_thu_quyen", "ROLE_PERMISSION_MATRIX.csv"
))

# Ánh xạ vai trò được phép cấp theo ROLE_GRANT_RULES.md.
DEFAULT_GRANTABLE_ROLES: Dict[str, List[str]] = {
    "WORKSPACE_OWNER": [
        "EXECUTIVE", "DEPARTMENT_MANAGER", "TEAM_LEAD", "RESEARCHER",
        "STRATEGIST", "VIDEO_EDITOR", "PUBLISHER", "ANALYST", "FINANCE_MANAGER",
        "CLIENT_APPROVER", "AUDITOR", "GUEST"
    ],
    "EXECUTIVE": [
        "TEAM_LEAD", "RESEARCHER", "STRATEGIST", "VIDEO_EDITOR", "ANALYST", "GUEST"
    ],
    "DEPARTMENT_MANAGER": [
        "TEAM_LEAD", "RESEARCHER", "STRATEGIST", "VIDEO_EDITOR", "ANALYST", "GUEST"
    ],
    "TEAM_LEAD": [
        "RESEARCHER", "STRATEGIST", "VIDEO_EDITOR", "GUEST"
    ],
    "RESEARCHER": [],
    "STRATEGIST": [],
    "VIDEO_EDITOR": [],
    "PUBLISHER": [],
    "ANALYST": [],
    "FINANCE_MANAGER": [],
    "CLIENT_APPROVER": [],
    "AUDITOR": [],
    "GUEST": [],
    "PLATFORM_OPS": [],
    "SERVICE_PRINCIPAL": []
}

class PolicyRegistry:
    def __init__(self):
        self._permissions: Dict[str, dict] = {}
        self._role_matrix: Dict[str, Dict[str, str]] = {} # role_code -> {action_key: scope}
        self.load()

    def load(self):
        # 1. Load PERMISSION_REGISTRY.json
        if os.path.exists(REGISTRY_FILE):
            with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                perms = data.get("permissions", [])
                for p in perms:
                    act = p.get("action") or p.get("action_key")
                    if act:
                        self._permissions[act] = p

        # 2. Load ROLE_PERMISSION_MATRIX.csv
        if os.path.exists(MATRIX_FILE):
            with open(MATRIX_FILE, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    action_key = row.get("permission") or row.get("action_key")
                    if not action_key:
                        continue
                    for role_col, scope_val in row.items():
                        if role_col in ["permission", "action_key", "risk", "risk_tier", "notes", "immutable_constraints"]:
                            continue
                        if role_col not in self._role_matrix:
                            self._role_matrix[role_col] = {}
                        if scope_val and scope_val.strip() not in ("-", "NONE"):
                            self._role_matrix[role_col][action_key] = scope_val.strip()

    def get_permission(self, action_key: str) -> Optional[dict]:
        return self._permissions.get(action_key)

    def is_action_registered(self, action_key: str) -> bool:
        return action_key in self._permissions

    def get_role_action_scope(self, role_code: str, action_key: str) -> Optional[str]:
        """Trả về phạm vi tối đa theo ngữ nghĩa; mã ma trận không rõ sẽ bị từ chối."""
        raw_scope = self._role_matrix.get(role_code, {}).get(action_key)
        if raw_scope is None:
            return None
        if raw_scope in _SCOPE_CODES.values():
            return raw_scope
        return _SCOPE_CODES.get(raw_scope)

    def get_grantable_roles(self, grantor_role: str) -> List[str]:
        return DEFAULT_GRANTABLE_ROLES.get(grantor_role, [])

    def can_grant_role(self, grantor_role: str, target_role: str) -> bool:
        return target_role in self.get_grantable_roles(grantor_role)

registry = PolicyRegistry()
