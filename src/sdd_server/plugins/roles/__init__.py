"""Built-in role plugins for SDD.

This package contains the 6 built-in role plugins:
- ArchitectRole: System architecture design (priority 10)
- UIDesignerRole: UI/UX design review (priority 20)
- InterfaceDesignerRole: API/interface design (priority 20)
- SecurityAnalystRole: Security analysis (priority 30)
- EdgeCaseAnalystRole: Edge case analysis (priority 40)
- SeniorDeveloperRole: Implementation review (priority 50)

Role execution order is determined by:
1. Dependencies (a role runs after its dependencies)
2. Priority (lower priority number = runs first within same stage)

Dependency graph:
    Architect (10)
        ├── UI Designer (20)
        └── Interface Designer (20)
                └── Security Analyst (30)
                        └── Edge Case Analyst (40)
                                └── Senior Developer (50)
"""

from sdd_server.plugins.roles.architect import ArchitectRole
from sdd_server.plugins.roles.edge_case_analyst import EdgeCaseAnalystRole
from sdd_server.plugins.roles.interface_designer import InterfaceDesignerRole
from sdd_server.plugins.roles.security_analyst import SecurityAnalystRole
from sdd_server.plugins.roles.senior_developer import SeniorDeveloperRole
from sdd_server.plugins.roles.ui_designer import UIDesignerRole

__all__ = [
    "ArchitectRole",
    "EdgeCaseAnalystRole",
    "InterfaceDesignerRole",
    "SecurityAnalystRole",
    "SeniorDeveloperRole",
    "UIDesignerRole",
]

# List of all built-in role classes for discovery
BUILTIN_ROLES = [
    ArchitectRole,
    UIDesignerRole,
    InterfaceDesignerRole,
    SecurityAnalystRole,
    EdgeCaseAnalystRole,
    SeniorDeveloperRole,
]
