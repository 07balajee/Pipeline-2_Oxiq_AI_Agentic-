import unittest
import ast
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

class TestArchitectureInvariants(unittest.TestCase):
    def get_py_files(self, relative_dir: str):
        target_dir = PROJECT_ROOT / relative_dir
        if not target_dir.exists():
            return []
        return list(target_dir.rglob("*.py"))

    def check_file_imports(self, filepath: Path, forbidden_modules: list, forbidden_names: list):
        with open(filepath, "r", encoding="utf-8") as f:
            code = f.read()
        
        tree = ast.parse(code, filename=str(filepath))
        violations = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    for fmod in forbidden_modules:
                        if name == fmod or name.startswith(fmod + "."):
                            violations.append(f"Import '{name}' violates rule '{fmod}' at line {node.lineno}")
                    for fname in forbidden_names:
                        if name == fname:
                            violations.append(f"Import '{name}' violates forbidden name '{fname}' at line {node.lineno}")
                            
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for fmod in forbidden_modules:
                    if module == fmod or module.startswith(fmod + "."):
                        violations.append(f"ImportFrom module '{module}' violates rule '{fmod}' at line {node.lineno}")
                for alias in node.names:
                    name = alias.name
                    full_name = f"{module}.{name}" if module else name
                    for fname in forbidden_names:
                        if name == fname or full_name.endswith(fname):
                            violations.append(f"ImportFrom name '{name}' from '{module}' violates forbidden name '{fname}' at line {node.lineno}")
                            
        return violations

    def test_master_domain_isolation(self):
        """
        agents/master/** must have ZERO imports of worker implementations (A6, A7, A8).
        """
        py_files = self.get_py_files("agents/master")
        forbidden_mods = ["agents.agent6", "agents.agent7", "agents.agent8"]
        forbidden_names = ["InterviewInvitationAgent", "TechnicalInterviewAgent", "HRInterviewAgent"]
        
        all_violations = []
        for py_file in py_files:
            v = self.check_file_imports(py_file, forbidden_mods, forbidden_names)
            if v:
                all_violations.append(f"In {py_file.relative_to(PROJECT_ROOT)}:\n  " + "\n  ".join(v))
                
        self.assertEqual(len(all_violations), 0, "\n".join(all_violations))

    def test_master_service_api_isolation(self):
        """
        services/master_api/** must have ZERO imports of worker implementations (A6, A7, A8).
        """
        py_files = self.get_py_files("services/master_api")
        forbidden_mods = ["agents.agent6", "agents.agent7", "agents.agent8"]
        forbidden_names = ["InterviewInvitationAgent", "TechnicalInterviewAgent", "HRInterviewAgent"]
        
        all_violations = []
        for py_file in py_files:
            v = self.check_file_imports(py_file, forbidden_mods, forbidden_names)
            if v:
                all_violations.append(f"In {py_file.relative_to(PROJECT_ROOT)}:\n  " + "\n  ".join(v))
                
        self.assertEqual(len(all_violations), 0, "\n".join(all_violations))

    def test_agent6_peer_and_master_isolation(self):
        """
        agents/agent6/** and services/agent6_api/** must NOT import agent7, agent8, or Master.
        """
        py_files = self.get_py_files("agents/agent6") + self.get_py_files("services/agent6_api")
        forbidden_mods = ["agents.agent7", "agents.agent8", "agents.master", "services.master_api"]
        forbidden_names = ["TechnicalInterviewAgent", "HRInterviewAgent", "MasterAgent"]
        
        all_violations = []
        for py_file in py_files:
            v = self.check_file_imports(py_file, forbidden_mods, forbidden_names)
            if v:
                all_violations.append(f"In {py_file.relative_to(PROJECT_ROOT)}:\n  " + "\n  ".join(v))
                
        self.assertEqual(len(all_violations), 0, "\n".join(all_violations))

    def test_agent7_peer_and_master_isolation(self):
        """
        agents/agent7/** and services/agent7_api/** must NOT import agent6, agent8, or Master.
        """
        py_files = self.get_py_files("agents/agent7") + self.get_py_files("services/agent7_api")
        forbidden_mods = ["agents.agent6", "agents.agent8", "agents.master", "services.master_api"]
        forbidden_names = ["InterviewInvitationAgent", "HRInterviewAgent", "MasterAgent"]
        
        all_violations = []
        for py_file in py_files:
            v = self.check_file_imports(py_file, forbidden_mods, forbidden_names)
            if v:
                all_violations.append(f"In {py_file.relative_to(PROJECT_ROOT)}:\n  " + "\n  ".join(v))
                
        self.assertEqual(len(all_violations), 0, "\n".join(all_violations))

    def test_agent8_peer_and_master_isolation(self):
        """
        agents/agent8/** and services/agent8_api/** must NOT import agent6, agent7, or Master.
        """
        py_files = self.get_py_files("agents/agent8") + self.get_py_files("services/agent8_api")
        forbidden_mods = ["agents.agent6", "agents.agent7", "agents.master", "services.master_api"]
        forbidden_names = ["InterviewInvitationAgent", "TechnicalInterviewAgent", "MasterAgent"]
        
        all_violations = []
        for py_file in py_files:
            v = self.check_file_imports(py_file, forbidden_mods, forbidden_names)
            if v:
                all_violations.append(f"In {py_file.relative_to(PROJECT_ROOT)}:\n  " + "\n  ".join(v))
                
        self.assertEqual(len(all_violations), 0, "\n".join(all_violations))

if __name__ == "__main__":
    unittest.main()
