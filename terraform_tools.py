#!/usr/bin/env python3
"""
Terraform Tools Integration
Provides unified interface for tfsec, tflint, and terraform validate
"""

import os
import json
import subprocess
import tempfile
from typing import Dict, List, Any, Optional
from pathlib import Path


class TerraformTools:
    """Unified Terraform validation, linting, and security scanning tool."""
    
    def __init__(self):
        self.tools_available = self._check_tool_availability()
        
    def _check_tool_availability(self) -> Dict[str, bool]:
        """Check which Terraform tools are available."""
        tools = {}
        
        # Check terraform
        try:
            result = subprocess.run(['terraform', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            tools['terraform'] = result.returncode == 0
        except:
            tools['terraform'] = False
            
        # Check tfsec
        try:
            result = subprocess.run(['tfsec', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            tools['tfsec'] = result.returncode == 0
        except:
            tools['tfsec'] = False
            
        # Check tflint
        try:
            result = subprocess.run(['tflint', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            tools['tflint'] = result.returncode == 0
        except:
            tools['tflint'] = False
            
        return tools
    
    def validate_file(self, file_path: str) -> Dict[str, Any]:
        """Validate a single Terraform file using all available tools."""
        if not os.path.exists(file_path):
            return {
                "file": file_path,
                "valid": False,
                "errors": ["File not found"],
                "terraform_validate": {"valid": False, "errors": ["File not found"]},
                "tfsec_results": {"issues": []},
                "tflint_results": {"issues": []}
            }
        
        results = {
            "file": file_path,
            "valid": True,
            "errors": [],
            "terraform_validate": {"valid": True, "errors": []},
            "tfsec_results": {"issues": []},
            "tflint_results": {"issues": []}
        }
        
        # Run terraform validate
        if self.tools_available.get('terraform', False):
            tf_result = self._run_terraform_validate(file_path)
            results["terraform_validate"] = tf_result
            if not tf_result["valid"]:
                results["valid"] = False
                results["errors"].extend(tf_result["errors"])
        
        # Run tfsec
        if self.tools_available.get('tfsec', False):
            tfsec_result = self._run_tfsec(file_path)
            results["tfsec_results"] = tfsec_result
            if tfsec_result["issues"]:
                results["valid"] = False  # Security issues make it invalid
        
        # Run tflint
        if self.tools_available.get('tflint', False):
            tflint_result = self._run_tflint(file_path)
            results["tflint_results"] = tflint_result
        
        return results
    
    def _run_terraform_validate(self, file_path: str) -> Dict[str, Any]:
        """Run terraform validate on a file."""
        try:
            # Create temporary directory for terraform init
            with tempfile.TemporaryDirectory() as temp_dir:
                # Copy file to temp directory
                file_name = os.path.basename(file_path)
                temp_file = os.path.join(temp_dir, file_name)
                
                with open(file_path, 'r') as src, open(temp_file, 'w') as dst:
                    dst.write(src.read())
                
                # Initialize terraform in temp directory
                init_result = subprocess.run(
                    ['terraform', 'init'],
                    cwd=temp_dir,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                # Run terraform validate
                validate_result = subprocess.run(
                    ['terraform', 'validate', '-json'],
                    cwd=temp_dir,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if validate_result.returncode == 0:
                    try:
                        output = json.loads(validate_result.stdout)
                        return {
                            "valid": output.get("valid", True),
                            "errors": [d.get("summary", "") for d in output.get("diagnostics", [])]
                        }
                    except json.JSONDecodeError:
                        return {"valid": True, "errors": []}
                else:
                    return {
                        "valid": False,
                        "errors": [validate_result.stderr.strip() if validate_result.stderr else "Validation failed"]
                    }
                    
        except subprocess.TimeoutExpired:
            return {"valid": False, "errors": ["Terraform validate timeout"]}
        except Exception as e:
            return {"valid": False, "errors": [f"Terraform validate error: {str(e)}"]}
    
    def _run_tfsec(self, file_path: str) -> Dict[str, Any]:
        """Run tfsec security scanning on a file."""
        try:
            result = subprocess.run(
                ['tfsec', '--format', 'json', '--soft-fail', file_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.stdout:
                try:
                    output = json.loads(result.stdout)
                    issues = []
                    
                    # Extract security issues
                    for check in output.get("results", []):
                        if check.get("status") == "FAILED":
                            issues.append({
                                "rule_id": check.get("rule_id", "unknown"),
                                "severity": check.get("severity", "unknown"),
                                "description": check.get("description", ""),
                                "resolution": check.get("resolution", ""),
                                "location": check.get("location", {})
                            })
                    
                    return {"issues": issues}
                except json.JSONDecodeError:
                    return {"issues": []}
            else:
                return {"issues": []}
                
        except subprocess.TimeoutExpired:
            return {"issues": [{"rule_id": "timeout", "severity": "ERROR", "description": "tfsec timeout"}]}
        except Exception as e:
            return {"issues": [{"rule_id": "error", "severity": "ERROR", "description": f"tfsec error: {str(e)}"}]}
    
    def _run_tflint(self, file_path: str) -> Dict[str, Any]:
        """Run tflint on a file."""
        try:
            # Get directory containing the file
            file_dir = os.path.dirname(file_path)
            
            result = subprocess.run(
                ['tflint', '--format', 'json', '--chdir', file_dir],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.stdout:
                try:
                    output = json.loads(result.stdout)
                    issues = []
                    
                    # Extract linting issues
                    for issue in output.get("issues", []):
                        issues.append({
                            "rule": issue.get("rule", {}).get("name", "unknown"),
                            "severity": issue.get("rule", {}).get("severity", "unknown"),
                            "message": issue.get("message", ""),
                            "filename": issue.get("range", {}).get("filename", ""),
                            "line": issue.get("range", {}).get("start", {}).get("line", 0)
                        })
                    
                    return {"issues": issues}
                except json.JSONDecodeError:
                    return {"issues": []}
            else:
                return {"issues": []}
                
        except subprocess.TimeoutExpired:
            return {"issues": [{"rule": "timeout", "severity": "error", "message": "tflint timeout"}]}
        except Exception as e:
            return {"issues": [{"rule": "error", "severity": "error", "message": f"tflint error: {str(e)}"}]}
    
    def batch_validate(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        """Validate multiple Terraform files."""
        results = []
        for file_path in file_paths:
            try:
                result = self.validate_file(file_path)
                results.append(result)
            except Exception as e:
                results.append({
                    "file": file_path,
                    "valid": False,
                    "errors": [f"Batch validation error: {str(e)}"],
                    "terraform_validate": {"valid": False, "errors": [str(e)]},
                    "tfsec_results": {"issues": []},
                    "tflint_results": {"issues": []}
                })
        return results
    
    def get_available_tools(self) -> Dict[str, bool]:
        """Get status of available Terraform tools."""
        return self.tools_available.copy()
    
    def validate_directory(self, directory_path: str) -> List[Dict[str, Any]]:
        """Validate all Terraform files in a directory."""
        tf_files = self._find_terraform_files(directory_path)
        return self.batch_validate(tf_files)
    
    def _find_terraform_files(self, directory_path: str) -> List[str]:
        """Find all Terraform files in a directory."""
        tf_files = []
        
        for root, dirs, files in os.walk(directory_path):
            # Skip .terraform directories
            dirs[:] = [d for d in dirs if d != '.terraform']
            
            for file in files:
                if file.endswith(('.tf', '.tfvars')):
                    tf_files.append(os.path.join(root, file))
        
        return tf_files 