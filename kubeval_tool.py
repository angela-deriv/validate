import subprocess
import json
import yaml
import os
import tempfile
from typing import List, Dict, Any, Optional
from pathlib import Path

#jdiwj
class KubevalTool:
    """
    A wrapper around kubeval for validating Kubernetes YAML files.
    """
    
    def __init__(self, schema_location: Optional[str] = None):
        self.schema_location = schema_location or "https://raw.githubusercontent.com/yannh/kubernetes-json-schema/master/"
        self._check_kubeval_installation()
    
    def _check_kubeval_installation(self) -> bool:
        """Check if kubeval is installed and accessible."""
        try:
            result = subprocess.run(['kubeval', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                raise RuntimeError("kubeval is not properly installed or not in PATH")
            return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            raise RuntimeError("kubeval is not installed. Please install it from: https://github.com/instrumenta/kubeval")
    
    def validate_file(self, file_path: str) -> Dict[str, Any]:
        """
        Validate a single Kubernetes YAML file using kubeval.
        
        Args:
            file_path: Path to the YAML file to validate
            
        Returns:
            Dict containing validation results
        """
        if not os.path.exists(file_path):
            return {
                "file": file_path,
                "valid": False,
                "errors": [f"File not found: {file_path}"]
            }
        
        try:
            # Run kubeval with JSON output for easier parsing
            cmd = [
                'kubeval',
                '--output', 'json',
                '--schema-location', self.schema_location,
                file_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            # Parse kubeval output
            if result.stdout:
                try:
                    kubeval_output = json.loads(result.stdout)
                except json.JSONDecodeError:
                    kubeval_output = {"results": []}
            else:
                kubeval_output = {"results": []}
            
            return {
                "file": file_path,
                "valid": result.returncode == 0,
                "kubeval_output": kubeval_output,
                "errors": result.stderr.split('\n') if result.stderr else [],
                "return_code": result.returncode
            }
            
        except subprocess.TimeoutExpired:
            return {
                "file": file_path,
                "valid": False,
                "errors": ["Validation timeout after 30 seconds"]
            }
        except Exception as e:
            return {
                "file": file_path,
                "valid": False,
                "errors": [f"Validation error: {str(e)}"]
            }
    
    def validate_directory(self, directory_path: str, recursive: bool = True) -> List[Dict[str, Any]]:
        """
        Validate all YAML files in a directory.
        
        Args:
            directory_path: Path to directory containing YAML files
            recursive: Whether to search subdirectories
            
        Returns:
            List of validation results for each file
        """
        yaml_files = self._find_yaml_files(directory_path, recursive)
        results = []
        
        for yaml_file in yaml_files:
            result = self.validate_file(yaml_file)
            results.append(result)
        
        return results
    
    def validate_content(self, yaml_content: str, filename: str = "temp.yaml") -> Dict[str, Any]:
        """
        Validate YAML content directly without saving to a permanent file.
        
        Args:
            yaml_content: YAML content as string
            filename: Temporary filename for validation
            
        Returns:
            Dict containing validation results
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
            temp_file.write(yaml_content)
            temp_file_path = temp_file.name
        
        try:
            result = self.validate_file(temp_file_path)
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
    
    def batch_validate(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        """
        Validate multiple files in batch.
        
        Args:
            file_paths: List of file paths to validate
            
        Returns:
            List of validation results
        """
        results = []
        for file_path in file_paths:
            result = self.validate_file(file_path)
            results.append(result)
        return results 