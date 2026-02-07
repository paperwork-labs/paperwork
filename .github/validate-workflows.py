#!/usr/bin/env python3
"""
AxiomFolio V2 - CI/CD Workflow Validation Script
Validates that all workflows are properly configured and ready for use.
"""

import os
import yaml
import json
import sys
from pathlib import Path

def validate_workflow_file(workflow_path):
    """Validate a single workflow YAML file."""
    try:
        with open(workflow_path, 'r') as f:
            workflow = yaml.safe_load(f)
        
        # Check required fields
        # Note: 'on' becomes True in YAML parsing due to boolean interpretation
        required_fields = ['name', 'jobs']
        for field in required_fields:
            if field not in workflow:
                return False, f"Missing required field: {field}"
        
        # Check for trigger field ('on' becomes True in YAML)
        if True not in workflow and 'on' not in workflow:
            return False, "Missing trigger field ('on')"
        
        # Check job structure
        if not isinstance(workflow['jobs'], dict):
            return False, "Jobs must be a dictionary"
        
        for job_name, job_config in workflow['jobs'].items():
            if 'runs-on' not in job_config:
                return False, f"Job {job_name} missing 'runs-on'"
            if 'steps' not in job_config:
                return False, f"Job {job_name} missing 'steps'"
        
        return True, "Valid workflow"
        
    except yaml.YAMLError as e:
        return False, f"YAML parsing error: {e}"
    except Exception as e:
        return False, f"Validation error: {e}"

def check_workflow_dependencies():
    """Check that workflow dependencies are available."""
    dependencies = {
        'Python requirements': 'requirements.txt',
        'Frontend package': 'frontend/package.json',
        'Docker backend': 'Dockerfile.backend',
        'Docker frontend': 'Dockerfile.frontend',
        'Docker compose': 'docker-compose.yml',
        'V2 models': 'backend/models_v2/__init__.py',
        'V2 tests': 'backend/tests_v2/conftest.py'
    }
    
    missing = []
    for name, path in dependencies.items():
        if not os.path.exists(path):
            missing.append(f"{name}: {path}")
    
    return missing

def validate_test_structure():
    """Validate V2 test structure is in place."""
    required_test_dirs = [
        'backend/tests_v2/unit/models',
        'backend/tests_v2/unit/services/analysis',
        'backend/tests_v2/unit/services/portfolio',
        'backend/tests_v2/integration',
        'backend/tests_v2/api',
        'backend/tests_v2/performance'
    ]
    
    missing_dirs = []
    for test_dir in required_test_dirs:
        if not os.path.exists(test_dir):
            missing_dirs.append(test_dir)
    
    return missing_dirs

def main():
    """Main validation function."""
    print("🔍 AxiomFolio V2 - CI/CD Workflow Validation")
    print("=" * 50)
    
    workflows_dir = Path('.github/workflows')
    
    if not workflows_dir.exists():
        print("❌ .github/workflows directory not found!")
        sys.exit(1)
    
    # Expected workflows
    expected_workflows = {
        'ci.yml': 'Continuous Integration',
        'cd.yml': 'Continuous Deployment', 
        'security.yml': 'Security Scanning',
        'performance.yml': 'Performance Monitoring'
    }
    
    print("\n📋 Checking Workflow Files:")
    all_valid = True
    
    for filename, description in expected_workflows.items():
        workflow_path = workflows_dir / filename
        
        if workflow_path.exists():
            is_valid, message = validate_workflow_file(workflow_path)
            status = "✅" if is_valid else "❌"
            print(f"  {status} {description} ({filename}): {message}")
            if not is_valid:
                all_valid = False
        else:
            print(f"  ❌ {description} ({filename}): Missing file")
            all_valid = False
    
    print("\n📦 Checking Dependencies:")
    missing_deps = check_workflow_dependencies()
    if missing_deps:
        print("  ❌ Missing dependencies:")
        for dep in missing_deps:
            print(f"    - {dep}")
        all_valid = False
    else:
        print("  ✅ All dependencies found")
    
    print("\n🧪 Checking Test Structure:")
    missing_test_dirs = validate_test_structure()
    if missing_test_dirs:
        print("  ❌ Missing test directories:")
        for test_dir in missing_test_dirs:
            print(f"    - {test_dir}")
        all_valid = False
    else:
        print("  ✅ V2 test structure complete")
    
    print("\n📊 Validation Summary:")
    if all_valid:
        print("✅ All workflows are properly configured!")
        print("🚀 Ready for CI/CD automation!")
        print("\nNext steps:")
        print("  1. Commit and push workflows to repository")
        print("  2. Configure GitHub repository environments")
        print("  3. Set up required secrets for deployment")
        print("  4. Make a test commit to trigger CI")
        sys.exit(0)
    else:
        print("❌ Some issues found - fix before using workflows")
        print("\nFix the issues above and run validation again")
        sys.exit(1)

if __name__ == "__main__":
    main() 