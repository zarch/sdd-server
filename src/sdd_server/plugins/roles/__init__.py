"""Built-in role plugins for SDD.

This package contains the 11 built-in role plugins:
- SpecLinterRole: Pre-flight spec structure and consistency validator (priority 5)
- ArchitectRole: System architecture design (priority 10)
- UIDesignerRole: UI/UX design review (priority 20)
- InterfaceDesignerRole: API/interface design (priority 20)
- SecurityAnalystRole: Security analysis (priority 30)
- EdgeCaseAnalystRole: Edge case analysis (priority 40)
- SeniorDeveloperRole: Implementation review (priority 50)
- QAEngineerRole: Acceptance testing and QA report (priority 60)
- TechWriterRole: Documentation generation (priority 60)
- DevOpsEngineerRole: CI/CD and deployment review (priority 60)
- ProductOwnerRole: Release sign-off and SHIP/HOLD verdict (priority 80)

Role execution order is determined by:
1. Dependencies (a role runs after its dependencies)
2. Priority (lower priority number = runs first within same stage)

Dependency graph:
    Spec Linter (5)
        └── Architect (10)
                ├── UI Designer (20)
                └── Interface Designer (20)
                        └── Security Analyst (30)
                                └── Edge Case Analyst (40)
                                        └── Senior Developer (50)
                                                ├── QA Engineer (60)
                                                ├── Tech Writer (60)
                                                └── DevOps Engineer (60)
                                                        └── Product Owner (80)
"""

from sdd_server.plugins.roles.architect import ArchitectRole
from sdd_server.plugins.roles.devops_engineer import DevOpsEngineerRole
from sdd_server.plugins.roles.edge_case_analyst import EdgeCaseAnalystRole
from sdd_server.plugins.roles.interface_designer import InterfaceDesignerRole
from sdd_server.plugins.roles.product_owner import ProductOwnerRole
from sdd_server.plugins.roles.qa_engineer import QAEngineerRole
from sdd_server.plugins.roles.security_analyst import SecurityAnalystRole
from sdd_server.plugins.roles.senior_developer import SeniorDeveloperRole
from sdd_server.plugins.roles.spec_linter import SpecLinterRole
from sdd_server.plugins.roles.tech_writer import TechWriterRole
from sdd_server.plugins.roles.ui_designer import UIDesignerRole

__all__ = [
    "ArchitectRole",
    "DevOpsEngineerRole",
    "EdgeCaseAnalystRole",
    "InterfaceDesignerRole",
    "ProductOwnerRole",
    "QAEngineerRole",
    "SecurityAnalystRole",
    "SeniorDeveloperRole",
    "SpecLinterRole",
    "TechWriterRole",
    "UIDesignerRole",
]

# List of all built-in role classes for discovery
BUILTIN_ROLES = [
    SpecLinterRole,
    ArchitectRole,
    UIDesignerRole,
    InterfaceDesignerRole,
    SecurityAnalystRole,
    EdgeCaseAnalystRole,
    SeniorDeveloperRole,
    QAEngineerRole,
    TechWriterRole,
    DevOpsEngineerRole,
    ProductOwnerRole,
]
