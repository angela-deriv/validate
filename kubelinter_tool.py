import subprocess
import json
import yaml
import os
import tempfile
from typing import List, Dict, Any, Optional
from pathlib import Path


class KubeLinterTool:
    """
    A wrapper around kube-linter for linting Kubernetes YAML files.
    """
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file
        self._check_kubelinter_installation()
    
    def _check_kubelinter_installation(self) -> bool:
        """Check if kube-linter is installed and accessible."""
        try:
            result = subprocess.run(['./kube-linter', 'version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                raise RuntimeError("kube-linter is not properly installed or not accessible")
            return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            raise RuntimeError("kube-linter is not installed. Please install it from: https://github.com/stackrox/kube-linter")
    
    def lint_file(self, file_path: str) -> Dict[str, Any]:
        """
        Lint a single Kubernetes YAML file using kube-linter.
        
        Args:
            file_path: Path to the YAML file to lint
            
        Returns:
            Dict containing linting results
        """
        if not os.path.exists(file_path):
            return {
                "file": file_path,
                "valid": False,
                "kubelinter_output": {"Reports": []},
                "errors": [f"File not found: {file_path}"]
            }
        
        try:
            # Run kube-linter with JSON output for easier parsing
            cmd = ['./kube-linter', 'lint', '--format', 'json', file_path]
            
            if self.config_file:
                cmd.extend(['--config', self.config_file])
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            # Parse kube-linter output
            if result.stdout:
                try:
                    kubelinter_output = json.loads(result.stdout)
                except json.JSONDecodeError:
                    kubelinter_output = {"Reports": []}
            else:
                kubelinter_output = {"Reports": []}
            
            # kube-linter returns 0 when no issues found, 1 when issues found
            return {
                "file": file_path,
                "valid": result.returncode == 0,
                "kubelinter_output": kubelinter_output,
                "errors": result.stderr.split('\n') if result.stderr else [],
                "return_code": result.returncode
            }
            
        except subprocess.TimeoutExpired:
            return {
                "file": file_path,
                "valid": False,
                "kubelinter_output": {"Reports": []},
                "errors": ["Linting timeout after 30 seconds"]
            }
        except Exception as e:
            return {
                "file": file_path,
                "valid": False,
                "kubelinter_output": {"Reports": []},
                "errors": [f"Linting error: {str(e)}"]
            }
    
    def lint_directory(self, directory_path: str, recursive: bool = True) -> List[Dict[str, Any]]:
        """
        Lint all YAML files in a directory.
        
        Args:
            directory_path: Path to directory containing YAML files
            recursive: Whether to search subdirectories
            
        Returns:
            List of linting results for each file
        """
        yaml_files = self._find_yaml_files(directory_path, recursive)
        results = []
        
        for yaml_file in yaml_files:
            result = self.lint_file(yaml_file)
            results.append(result)
        
        return results
    
    def lint_content(self, yaml_content: str, filename: str = "temp.yaml") -> Dict[str, Any]:
        """
        Lint YAML content directly without saving to a permanent file.
        
        Args:
            yaml_content: YAML content as string
            filename: Temporary filename for linting
            
        Returns:
            Dict containing linting results
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
            temp_file.write(yaml_content)
            temp_file_path = temp_file.name
        
        try:
            result = self.lint_file(temp_file_path)
            result["file"] = filename  # Use the provided filename instead of temp path
            return result
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
    
    def _find_yaml_files(self, directory_path: str, recursive: bool = True) -> List[str]:
        """Find all YAML files in a directory."""
        yaml_files = []
        path = Path(directory_path)
        
        if not path.exists():
            return yaml_files
        
        # Pattern for YAML files
        patterns = ['*.yaml', '*.yml']
        
        for pattern in patterns:
            if recursive:
                yaml_files.extend([str(f) for f in path.rglob(pattern)])
            else:
                yaml_files.extend([str(f) for f in path.glob(pattern)])
        
        return sorted(yaml_files)
    
    def batch_lint(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        """
        Lint multiple files in batch.
        
        Args:
            file_paths: List of file paths to lint
            
        Returns:
            List of linting results
        """
        results = []
        for file_path in file_paths:
            result = self.lint_file(file_path)
            results.append(result)
        return results
    
    def get_available_checks(self) -> List[str]:
        """
        Get list of available kube-linter checks.
        
        Returns:
            List of available check names
        """
        try:
            result = subprocess.run(['./kube-linter', 'checks', 'list', '--format', 'json'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and result.stdout:
                checks_data = json.loads(result.stdout)
                return [check.get('Name', '') for check in checks_data.get('Checks', [])]
            return []
        except Exception:
            return [] 