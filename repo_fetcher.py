import os
import tempfile
import shutil
from pathlib import Path
from typing import Optional, List
import subprocess


class RepoFetcher:
    """
    Handles fetching and managing git repositories for validation.
    """
    
    def __init__(self, repo_url: str):
        self.repo_url = repo_url
        self.local_path: Optional[str] = None
        self.temp_dir = None
    
    def clone_repo(self, target_dir: Optional[str] = None, branch: str = "main") -> str:
        """
        Clone the repository to a local directory.
        
        Args:
            target_dir: Directory to clone to. If None, uses a temp directory.
            branch: Git branch to checkout
            
        Returns:
            Path to the cloned repository
        """
        if target_dir is None:
            self.temp_dir = tempfile.mkdtemp(prefix="kubeval_repo_")
            target_dir = self.temp_dir
        
        try:
            # Clone the repository
            cmd = ['git', 'clone', '--depth', '1', '--branch', branch, self.repo_url, target_dir]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                # Try without specifying branch if the branch doesn't exist
                cmd = ['git', 'clone', '--depth', '1', self.repo_url, target_dir]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                
                if result.returncode != 0:
                    raise RuntimeError(f"Failed to clone repository: {result.stderr}")
            
            self.local_path = target_dir
            return target_dir
            
        except subprocess.TimeoutExpired:
            raise RuntimeError("Repository cloning timeout after 5 minutes")
        except Exception as e:
            if self.temp_dir and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
            raise RuntimeError(f"Error cloning repository: {str(e)}")
    
    def find_k8s_files(self, base_path: Optional[str] = None) -> List[str]:
        """
        Find all Kubernetes YAML files in the repository.
        
        Args:
            base_path: Base path to search from. Uses repo root if None.
            
        Returns:
            List of paths to Kubernetes YAML files
        """
        if base_path is None:
            base_path = self.local_path
        
        if not base_path or not os.path.exists(base_path):
            return []
        
        k8s_files = []
        search_path = Path(base_path)
        
        # Common Kubernetes file patterns
        yaml_patterns = ['*.yaml', '*.yml']
        
        for pattern in yaml_patterns:
            for file_path in search_path.rglob(pattern):
                if self._is_k8s_file(file_path):
                    k8s_files.append(str(file_path))
        
        return sorted(k8s_files)
    
    def _is_k8s_file(self, file_path: Path) -> bool:
        """
        Check if a YAML file is likely a Kubernetes manifest.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Skip very large files (likely not K8s manifests)
            if len(content) > 1024 * 1024:  # 1MB limit
                return False
            
            # Check for Kubernetes indicators
            k8s_indicators = [
                'apiVersion:', 'kind:', 'metadata:', 'spec:',
                'Deployment', 'Service', 'Pod', 'ConfigMap',
                'Secret', 'Ingress', 'StatefulSet', 'DaemonSet',
                'Job', 'CronJob', 'PersistentVolume', 'Namespace'
            ]
            
            content_lower = content.lower()
            indicator_count = sum(1 for indicator in k8s_indicators 
                                if indicator.lower() in content_lower)
            
            # If it has multiple Kubernetes indicators, it's probably a K8s file
            return indicator_count >= 2
            
        except (IOError, UnicodeDecodeError):
            return False
    
    def get_file_content(self, file_path: str) -> str:
        """
        Get the content of a file from the repository.
        
        Args:
            file_path: Path to the file
            
        Returns:
            File content as string
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            raise RuntimeError(f"Error reading file {file_path}: {str(e)}")
    
    def cleanup(self):
        """Clean up temporary files and directories."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                self.temp_dir = None
                self.local_path = None
            except Exception as e:
                print(f"Warning: Could not clean up temporary directory: {e}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.cleanup() 