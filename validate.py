#!/usr/bin/env python3
"""
Kubernetes Validation Tool with AI-Powered Report Generation

This tool uses kubeval to validate Kubernetes YAML files from a repository
and generates curated reports using an AI agent.

Environment Variables Required:
- API_KEY: AI service API key
- API_URL: AI service API URL  
- MODEL_NAME: AI model name
- REPO_URL: Git repository URL to validate

Optional Environment Variables:
- KUBEVAL_SCHEMA_LOCATION: Custom kubeval schema location
- OUTPUT_FORMAT: Report output format (json, text)
- REPORT_SEVERITY_LEVEL: Minimum severity level for reporting
"""

import os
import sys
import json
import argparse
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

from kubeval_tool import KubevalTool
from repo_fetcher import RepoFetcher
from validation_agent import ValidationAgent


class KubernetesValidator:
    """Main validator class that orchestrates the validation process."""
    
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # Required environment variables
        self.api_key = os.getenv('API_KEY')
        self.api_url = os.getenv('API_URL')
        self.model_name = os.getenv('MODEL_NAME')
        self.repo_url = os.getenv('REPO_URL')
        
        # Optional environment variables
        self.schema_location = os.getenv('KUBEVAL_SCHEMA_LOCATION')
        self.output_format = os.getenv('OUTPUT_FORMAT', 'text')
        self.severity_level = os.getenv('REPORT_SEVERITY_LEVEL', 'error')
        
        self._validate_env_vars()
        
        # Initialize components
        self.kubeval = KubevalTool(schema_location=self.schema_location)
        self.agent = ValidationAgent(self.api_key, self.api_url, self.model_name)
    
    def _validate_env_vars(self):
        """Validate that required environment variables are set."""
        required_vars = ['API_KEY', 'API_URL', 'MODEL_NAME', 'REPO_URL']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            print("❌ Missing required environment variables:")
            for var in missing_vars:
                print(f"   - {var}")
            print("\nCreate a .env file with the following variables:")
            print("API_KEY=your_api_key_here")
            print("API_URL=your_api_url_here") 
            print("MODEL_NAME=your_model_name_here")
            print("REPO_URL=https://github.com/your-org/your-repo")
            sys.exit(1)
    
    def validate_repository(self, repo_url: Optional[str] = None, 
                          branch: str = "main") -> dict:
        """
        Validate Kubernetes files in a repository.
        
        Args:
            repo_url: Repository URL (uses env var if not provided)
            branch: Git branch to validate
            
        Returns:
            Dictionary containing validation results and report
        """
        target_repo = repo_url or self.repo_url
        
        print(f"🔄 Starting validation for repository: {target_repo}")
        print(f"📋 Branch: {branch}")
        print("=" * 60)
        
        try:
            # Fetch repository
            with RepoFetcher(target_repo) as fetcher:
                print("📥 Cloning repository...")
                repo_path = fetcher.clone_repo(branch=branch)
                
                print("🔍 Finding Kubernetes files...")
                k8s_files = fetcher.find_k8s_files()
                
                if not k8s_files:
                    print("⚠️  No Kubernetes files found in repository")
                    return {
                        "status": "no_files",
                        "message": "No Kubernetes files found",
                        "validation_results": [],
                        "report": "No Kubernetes files found in the repository."
                    }
                
                print(f"📁 Found {len(k8s_files)} Kubernetes files")
                
                # Validate files
                print("✅ Running kubeval validation...")
                validation_results = self.kubeval.batch_validate(k8s_files)
                
                # Generate AI report
                print("🤖 Generating AI-powered report...")
                detailed_report = self.agent.generate_detailed_report(
                    validation_results, target_repo
                )
                
                # Print summary
                self._print_validation_summary(validation_results)
                
                return {
                    "status": "success",
                    "repository": target_repo,
                    "branch": branch,
                    "timestamp": datetime.now().isoformat(),
                    "validation_results": validation_results,
                    "report": detailed_report,
                    "files_validated": len(k8s_files)
                }
                
        except Exception as e:
            error_msg = f"❌ Validation failed: {str(e)}"
            print(error_msg)
            return {
                "status": "error",
                "error": str(e),
                "validation_results": [],
                "report": error_msg
            }
    
    def validate_local_files(self, file_paths: list) -> dict:
        """
        Validate local Kubernetes files.
        
        Args:
            file_paths: List of file paths to validate
            
        Returns:
            Dictionary containing validation results and report
        """
        print(f"🔄 Starting validation for {len(file_paths)} local files")
        print("=" * 60)
        
        try:
            # Validate files
            print("✅ Running kubeval validation...")
            validation_results = self.kubeval.batch_validate(file_paths)
            
            # Generate AI report
            print("🤖 Generating AI-powered report...")
            detailed_report = self.agent.generate_detailed_report(validation_results)
            
            # Print summary
            self._print_validation_summary(validation_results)
            
            return {
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "validation_results": validation_results,
                "report": detailed_report,
                "files_validated": len(file_paths)
            }
            
        except Exception as e:
            error_msg = f"❌ Validation failed: {str(e)}"
            print(error_msg)
            return {
                "status": "error",
                "error": str(e),
                "validation_results": [],
                "report": error_msg
            }
    
    def _print_validation_summary(self, validation_results: list):
        """Print a quick summary of validation results."""
        total_files = len(validation_results)
        valid_files = sum(1 for r in validation_results if r.get('valid', False))
        invalid_files = total_files - valid_files
        
        print(f"\n📊 Quick Summary:")
        print(f"   Total files: {total_files}")
        print(f"   Valid files: {valid_files}")
        print(f"   Invalid files: {invalid_files}")
        print(f"   Success rate: {(valid_files/total_files*100):.1f}%")
    
    def save_report(self, results: dict, output_file: str):
        """Save the validation results and report to a file."""
        try:
            if self.output_format.lower() == 'json':
                with open(output_file, 'w') as f:
                    json.dump(results, f, indent=2)
            else:
                with open(output_file, 'w') as f:
                    f.write(results.get('report', 'No report generated'))
            
            print(f"📄 Report saved to: {output_file}")
            
        except Exception as e:
            print(f"❌ Failed to save report: {str(e)}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Kubernetes Validation Tool with AI-Powered Reporting"
    )
    parser.add_argument(
        '--repo', '-r',
        help='Repository URL to validate (overrides env var)'
    )
    parser.add_argument(
        '--branch', '-b',
        default='main',
        help='Git branch to validate (default: main)'
    )
    parser.add_argument(
        '--files', '-f',
        nargs='+',
        help='Local files to validate'
    )
    parser.add_argument(
        '--output', '-o',
        help='Output file for the report'
    )
    parser.add_argument(
        '--format',
        choices=['json', 'text'],
        default='text',
        help='Output format (default: text)'
    )
    
    args = parser.parse_args()
    
    # Initialize validator
    try:
        validator = KubernetesValidator()
    except SystemExit:
        return 1
    
    # Override output format if specified
    if args.format:
        validator.output_format = args.format
    
    # Run validation
    if args.files:
        # Validate local files
        results = validator.validate_local_files(args.files)
    else:
        # Validate repository
        results = validator.validate_repository(
            repo_url=args.repo,
            branch=args.branch
        )
    
    # Print report to console
    print("\n" + "=" * 60)
    print(results.get('report', 'No report generated'))
    
    # Save to file if requested
    if args.output:
        validator.save_report(results, args.output)
    
    # Exit with appropriate code
    if results.get('status') == 'error':
        return 1
    elif results.get('status') == 'no_files':
        return 2
    else:
        # Check if there were validation failures
        validation_results = results.get('validation_results', [])
        invalid_count = sum(1 for r in validation_results if not r.get('valid', True))
        return 0 if invalid_count == 0 else 3


if __name__ == '__main__':
    sys.exit(main())
