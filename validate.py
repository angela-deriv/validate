#!/usr/bin/env python3
"""
Kubernetes Validation Tool with AI-Powered Report Generation

This tool uses kubeconform for schema validation and kube-linter for best practices
analysis of Kubernetes YAML files, then generates comprehensive reports using an AI agent.

Environment Variables Required:
- API_KEY: AI service API key
- API_URL: AI service API URL  
- MODEL_NAME: AI model name
- REPO_URL: Git repository URL to validate

Optional Environment Variables:
- KUBECONFORM_SCHEMA_LOCATION: Custom kubeconform schema location
- OUTPUT_FORMAT: Report output format (json, text)
- REPORT_SEVERITY_LEVEL: Minimum severity level for reporting
"""

import os
import sys
import json
import argparse
from datetime import datetime
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

from kubeval_tool import KubeconformTool
from kubelinter_tool import KubeLinterTool
from terraform_tools import TerraformTools
from repo_fetcher import RepoFetcher
from validation_agent import ValidationAgent


class KubernetesValidator:
    """Main validator class that orchestrates the comprehensive validation process."""
    
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # Required environment variables
        self.api_key = os.getenv('API_KEY')
        self.api_url = os.getenv('API_URL')
        self.model_name = os.getenv('MODEL_NAME')
        self.repo_url = os.getenv('REPO_URL')
        
        # Optional environment variables
        self.schema_location = os.getenv('KUBECONFORM_SCHEMA_LOCATION')
        self.output_format = os.getenv('OUTPUT_FORMAT', 'text')
        self.severity_level = os.getenv('REPORT_SEVERITY_LEVEL', 'error')
        
        self._validate_env_vars()
        
        # Initialize components
        self.kubeconform = KubeconformTool(schema_location=self.schema_location)
        self.kubelinter = KubeLinterTool()
        self.agent = ValidationAgent(self.api_key, self.api_url, self.model_name)
    
    def _validate_env_vars(self):
        """Validate that required environment variables are set."""
        required_vars = ['API_KEY', 'API_URL', 'MODEL_NAME']  # REPO_URL is now optional
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
            print("Please set these in your .env file or environment")
            sys.exit(1)
    
    def validate_repository(self, repo_url: str, branch: str = "main", 
                          batch_size: int = 10, output_file: Optional[str] = None,
                          single_batch: bool = False) -> Dict[str, Any]:
        """
        Validate all Kubernetes files in a repository with batch processing.
        If single_batch=True, only processes first batch and generates comprehensive report.
        """
        try:
            # Initialize repo fetcher and clone repository
            fetcher = RepoFetcher(repo_url)
            repo_path = fetcher.clone_repo(branch=branch)
            
            # Find all Kubernetes files
            print("🔍 Finding Kubernetes files...")
            k8s_files = fetcher.find_k8s_files()
            print(f"📁 Found {len(k8s_files)} Kubernetes files")
            
            if not k8s_files:
                return {"status": "error", "error": "No Kubernetes files found in repository"}
            
            target_repo = repo_url.replace('.git', '') if repo_url.endswith('.git') else repo_url
            
            if single_batch:
                return self._process_single_batch(k8s_files, batch_size, target_repo, branch, output_file)
            else:
                return self._process_all_batches(k8s_files, batch_size, target_repo, branch, output_file)
                
        except Exception as e:
            print(f"❌ Repository validation failed: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    def _process_single_batch(self, k8s_files: List[str], batch_size: int, 
                            target_repo: str, branch: str, output_file: Optional[str]) -> Dict[str, Any]:
        """Process only the first batch and generate comprehensive AI analysis"""
        
        print(f"\n🎯 SINGLE BATCH COMPREHENSIVE ANALYSIS")
        print("=" * 80)
        print(f"📊 Analyzing first {batch_size} files for detailed insights")
        print(f"🤖 Will generate comprehensive AI-powered report")
        print("=" * 80)
        
        # Take only the first batch
        batch_files = k8s_files[:batch_size]
        
        print(f"\n📦 Processing Single Batch ({len(batch_files)} files)...")
        print(f"Files: {', '.join([os.path.basename(f) for f in batch_files])}")
        
        try:
            # Process files individually to catch errors
            kubeconform_results = []
            kubelinter_results = []
            processed_files = []
            skipped_files = []
            
            print(f"\n   ✅ Running kubeconform schema validation...")
            for file_path in batch_files:
                try:
                    result = self.kubeconform.validate_file(file_path)
                    if result and isinstance(result, dict):
                        kubeconform_results.append(result)
                        processed_files.append(file_path)
                        print(f"      📁 {os.path.basename(file_path)}: {'✅ Valid' if result.get('valid') else '❌ Invalid'}")
                    else:
                        skipped_files.append(file_path)
                        print(f"      ⚠️  Skipped: {os.path.basename(file_path)}")
                except Exception as e:
                    skipped_files.append(file_path)
                    print(f"      ❌ Error: {os.path.basename(file_path)} - {str(e)[:50]}")
            
            print(f"\n   🔍 Running kube-linter best practices analysis...")
            for file_path in processed_files:  # Only analyze successfully validated files
                try:
                    result = self.kubelinter.lint_file(file_path)
                    if result and isinstance(result, dict):
                        kubelinter_results.append(result)
                        
                        # Show linting results
                        kubelinter_output = result.get('kubelinter_output', {})
                        reports = kubelinter_output.get('Reports', [])
                        print(f"      📁 {os.path.basename(file_path)}: {len(reports)} warnings")
                    else:
                        print(f"      ⚠️  Linting skipped: {os.path.basename(file_path)}")
                except Exception as e:
                    print(f"      ❌ Linting error: {os.path.basename(file_path)} - {str(e)[:50]}")
            
            # Calculate summary stats
            total_files = len(batch_files)
            processed_count = len(processed_files)
            valid_files = sum(1 for r in kubeconform_results if r.get('valid', False))
            invalid_files = processed_count - valid_files
            total_errors = sum(len(r.get('errors', [])) for r in kubeconform_results)
            total_warnings = sum(len(r.get('kubelinter_output', {}).get('Reports', [])) for r in kubelinter_results)
            
            print(f"\n📊 Single Batch Summary:")
            print(f"   Total files in batch: {total_files}")
            print(f"   Successfully processed: {processed_count}")
            print(f"   Valid files: {valid_files}")
            print(f"   Invalid files: {invalid_files}")
            print(f"   Schema errors: {total_errors}")
            print(f"   Best practice warnings: {total_warnings}")
            print(f"   Skipped files: {len(skipped_files)}")
            
            print(f"\n🤖 Generating comprehensive AI analysis...")
            
            # Generate comprehensive report using AI agent
            comprehensive_report = self.agent.generate_comprehensive_report(
                kubeconform_results, kubelinter_results, target_repo, output_file
            )
            
            print(f"✅ Comprehensive single-batch analysis complete!")
            if output_file:
                print(f"📄 Detailed report saved to: {output_file}")
            
            return {
                "status": "success",
                "analysis_type": "single_batch",
                "repository": target_repo,
                "branch": branch,
                "batch_size": batch_size,
                "total_files_in_repo": len(self.repo_fetcher.find_k8s_files() if hasattr(self, 'repo_fetcher') else []),
                "files_in_batch": total_files,
                "processed_files": processed_count,
                "valid_files": valid_files,
                "invalid_files": invalid_files,
                "schema_errors": total_errors,
                "best_practice_warnings": total_warnings,
                "skipped_files": len(skipped_files),
                "batch_files": [os.path.basename(f) for f in batch_files],
                "kubeconform_results": kubeconform_results,
                "kubelinter_results": kubelinter_results,
                "comprehensive_report": comprehensive_report,
                "success_rate": (valid_files / processed_count * 100) if processed_count > 0 else 0
            }
            
        except Exception as e:
            print(f"❌ Single batch analysis failed: {str(e)}")
            return {
                "status": "error",
                "analysis_type": "single_batch", 
                "error": str(e),
                "batch_files": [os.path.basename(f) for f in batch_files]
            }
    
    def _process_all_batches(self, k8s_files: List[str], batch_size: int,
                           target_repo: str, branch: str, output_file: Optional[str]) -> Dict[str, Any]:
        """Process all batches (existing functionality)"""
        
        print(f"🔄 Starting comprehensive batch validation for repository: {target_repo}")
        print(f"📋 Branch: {branch}")
        print(f"📦 Batch size: {batch_size} files per batch")
        print("=" * 80)
        
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
                        "kubeconform_results": [],
                        "kubelinter_results": [],
                        "report": "No Kubernetes files found in the repository."
                    }
                
                print(f"📁 Found {len(k8s_files)} Kubernetes files")
                
                # Process files in batches
                all_kubeconform_results = []
                all_kubelinter_results = []
                skipped_batches = []
                skipped_files = []
                batch_reports = []
                
                # Initialize output file with header if specified
                if output_file:
                    with open(output_file, 'w') as f:
                        f.write("=" * 100 + "\n")
                        f.write("🔄 KUBERNETES REPOSITORY BATCH ANALYSIS REPORT\n")
                        f.write("=" * 100 + "\n")
                        f.write(f"Repository: {target_repo}\n")
                        f.write(f"Branch: {branch}\n")
                        f.write(f"Batch Size: {batch_size}\n")
                        f.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                        f.write("=" * 100 + "\n\n")
                        f.write("📊 BATCH-BY-BATCH ANALYSIS\n")
                        f.write("=" * 100 + "\n\n")
                
                # Split files into batches
                batches = [k8s_files[i:i + batch_size] for i in range(0, len(k8s_files), batch_size)]
                total_batches = len(batches)
                
                print(f"🔄 Processing {total_batches} batches...")
                
                for batch_num, batch_files in enumerate(batches, 1):
                    print(f"\n📦 Processing batch {batch_num}/{total_batches} ({len(batch_files)} files)...")
                    
                    try:
                        # Process files individually within the batch to catch file-level errors
                        batch_kubeconform_results = []
                        batch_kubelinter_results = []
                        
                        print(f"   ✅ Running kubeconform schema validation...")
                        for file_path in batch_files:
                            try:
                                result = self.kubeconform.validate_file(file_path)
                                if result and isinstance(result, dict):
                                    batch_kubeconform_results.append(result)
                                else:
                                    print(f"      ⚠️  Skipping problematic file: {os.path.basename(file_path)}")
                                    skipped_files.append(file_path)
                            except Exception as e:
                                print(f"      ❌ Error processing {os.path.basename(file_path)}: {str(e)[:50]}...")
                                skipped_files.append(file_path)
                                continue
                        
                        print(f"   🔍 Running kube-linter best practices analysis...")
                        for file_path in batch_files:
                            if file_path not in skipped_files:  # Only process files that weren't skipped in kubeconform
                                try:
                                    result = self.kubelinter.lint_file(file_path)
                                    if result and isinstance(result, dict):
                                        batch_kubelinter_results.append(result)
                                    else:
                                        print(f"      ⚠️  Skipping problematic file: {os.path.basename(file_path)}")
                                        skipped_files.append(file_path)
                                except Exception as e:
                                    print(f"      ❌ Error linting {os.path.basename(file_path)}: {str(e)[:50]}...")
                                    skipped_files.append(file_path)
                                    continue
                        
                        # Add successful results to overall results
                        all_kubeconform_results.extend(batch_kubeconform_results)
                        all_kubelinter_results.extend(batch_kubelinter_results)
                        
                        # Show batch progress
                        batch_errors = sum(1 for r in batch_kubeconform_results if not r.get('valid', True))
                        batch_warnings = 0
                        for r in batch_kubelinter_results:
                            kubelinter_output = r.get('kubelinter_output')
                            if kubelinter_output:
                                reports = kubelinter_output.get('Reports', [])
                                if reports:
                                    batch_warnings += len(reports)
                        
                        print(f"   📊 Batch {batch_num} results: {batch_errors} errors, {batch_warnings} warnings")
                        
                        # Create and write batch report immediately to file
                        processed_files = set(
                            [r.get('file', '') for r in batch_kubeconform_results if r.get('file')] +
                            [r.get('file', '') for r in batch_kubelinter_results if r.get('file')]
                        )
                        
                        batch_report = f"""🔄 BATCH {batch_num}/{total_batches} ANALYSIS
{'='*50}
Files in Batch: {', '.join([os.path.basename(f) for f in batch_files])}
Files Successfully Processed: {len(processed_files)}
Schema Validation Errors: {batch_errors}
Best Practice Warnings: {batch_warnings}

"""
                        
                        # Add detailed issues
                        if batch_errors > 0:
                            batch_report += "🚨 SCHEMA VALIDATION ERRORS:\n"
                            for result in batch_kubeconform_results:
                                if not result.get('valid', True):
                                    file_name = os.path.basename(result.get('file', 'unknown'))
                                    errors = result.get('errors', [])
                                    batch_report += f"  📁 {file_name}:\n"
                                    for error in errors[:3]:  # Show first 3 errors
                                        batch_report += f"    • {error}\n"
                                    if len(errors) > 3:
                                        batch_report += f"    ... and {len(errors) - 3} more errors\n"
                            batch_report += "\n"
                        
                        if batch_warnings > 0:
                            batch_report += "⚠️  BEST PRACTICE WARNINGS:\n"
                            for result in batch_kubelinter_results:
                                kubelinter_output = result.get('kubelinter_output', {})
                                reports = kubelinter_output.get('Reports', [])
                                if reports:
                                    file_name = os.path.basename(result.get('file', 'unknown'))
                                    batch_report += f"  📁 {file_name}:\n"
                                    for report in reports[:3]:  # Show first 3 warnings
                                        check = report.get('Check', 'Unknown')
                                        message = report.get('Message', '')[:100]
                                        batch_report += f"    • {check}: {message}...\n"
                                    if len(reports) > 3:
                                        batch_report += f"    ... and {len(reports) - 3} more warnings\n"
                            batch_report += "\n"
                        
                        if batch_errors == 0 and batch_warnings == 0:
                            batch_report += "✅ No issues found in this batch!\n\n"
                        
                        batch_report += "=" * 100 + "\n\n"
                        
                        # Write batch report to file immediately
                        if output_file:
                            with open(output_file, 'a') as f:
                                f.write(batch_report)
                        
                        batch_reports.append(batch_report)
                        print(f"   ✅ Batch {batch_num} report written to file")
                        
                    except Exception as e:
                        print(f"   ❌ Batch {batch_num} failed: {str(e)}")
                        print(f"   ⏭️  Skipping problematic batch and continuing...")
                        
                        # Write error info to file
                        error_report = f"""🔄 BATCH {batch_num}/{total_batches} ANALYSIS
{'='*50}
Status: ❌ FAILED
Error: {str(e)}
Files in Batch: {', '.join([os.path.basename(f) for f in batch_files])}
{'='*100}

"""
                        if output_file:
                            with open(output_file, 'a') as f:
                                f.write(error_report)
                        
                        # Add to skipped batches for reporting
                        skipped_batches.append({
                            'batch_number': batch_num,
                            'files': [os.path.basename(f) for f in batch_files],
                            'error': str(e)
                        })
                        continue
                
                # Check if we have any results to process
                if not all_kubeconform_results and not all_kubelinter_results:
                    print(f"\n❌ No successful batches processed. All {total_batches} batches failed.")
                    return {
                        "status": "error", 
                        "error": "All batches failed during processing",
                        "skipped_batches": skipped_batches,
                        "skipped_files": skipped_files,
                        "kubeconform_results": [],
                        "kubelinter_results": [],
                        "report": "All batches failed during validation processing."
                    }
                
                successful_files = len(all_kubeconform_results) + len(all_kubelinter_results)
                total_processed_files = len(set(r.get('file', '') for r in all_kubeconform_results + all_kubelinter_results))
                
                print(f"\n🎯 Batch Processing Summary:")
                print(f"   ✅ Successful batches: {total_batches - len(skipped_batches)}/{total_batches}")
                print(f"   ⏭️  Skipped batches: {len(skipped_batches)}")
                print(f"   📁 Files processed: {total_processed_files}/{len(k8s_files)}")
                print(f"   ⚠️  Skipped files: {len(set(skipped_files))}")
                
                if skipped_batches:
                    print(f"   ⚠️  Skipped batches:")
                    for skip in skipped_batches:
                        print(f"      Batch {skip['batch_number']}: {', '.join(skip['files'][:3])}{'...' if len(skip['files']) > 3 else ''}")
                
                if skipped_files:
                    print(f"   ⚠️  Skipped individual files: {len(set(skipped_files))} files")
                
                print(f"\n🤖 Generating comprehensive AI-powered report from {total_processed_files} successfully processed files...")
                print("   📊 Analyzing combined results from all successful batches...")
                
                # Generate comprehensive AI report with all successful results
                detailed_report = self.agent.generate_comprehensive_report(
                    all_kubeconform_results, all_kubelinter_results, target_repo, output_file
                )
                
                # Compile final report with batch reports and processing notes
                final_report = detailed_report
                
                # Add batch-by-batch analysis if we have batch reports
                if batch_reports:
                    final_report += "\n\n" + "="*100
                    final_report += "\n📊 BATCH-BY-BATCH ANALYSIS DETAILS"
                    final_report += "\n" + "="*100
                    for report in batch_reports:
                        final_report += report
                
                # Add processing notes
                if skipped_batches or skipped_files:
                    processing_notes = f"\n\n⚠️  PROCESSING NOTES:\n"
                    if skipped_batches:
                        processing_notes += f"- {len(skipped_batches)} batches were skipped due to processing errors\n"
                    if skipped_files:
                        processing_notes += f"- {len(set(skipped_files))} individual files were skipped due to file-level errors\n"
                    processing_notes += f"- {total_processed_files} out of {len(k8s_files)} total files were successfully analyzed\n"
                    processing_notes += f"- Report generated from successfully processed files only\n"
                    
                    if skipped_files:
                        processing_notes += f"\nSkipped files (sample):\n"
                        for file_path in list(set(skipped_files))[:10]:  # Show first 10 unique skipped files
                            processing_notes += f"  • {os.path.basename(file_path)}\n"
                        if len(set(skipped_files)) > 10:
                            processing_notes += f"  ... and {len(set(skipped_files)) - 10} more files\n"
                    
                    final_report += processing_notes
                
                # Print comprehensive summary
                print("\n🏁 Final Repository Analysis:")
                self._print_comprehensive_summary(all_kubeconform_results, all_kubelinter_results)
                
                return {
                    "status": "success",
                    "repository": target_repo,
                    "branch": branch,
                    "timestamp": datetime.now().isoformat(),
                    "total_files": len(k8s_files),
                    "processed_files": total_processed_files,
                    "skipped_files": len(set(skipped_files)),
                    "batches_processed": total_batches - len(skipped_batches),
                    "batches_skipped": len(skipped_batches),
                    "batch_size": batch_size,
                    "skipped_batches": skipped_batches,
                    "skipped_file_list": list(set(skipped_files)),
                    "batch_reports": batch_reports,
                    "kubeconform_results": all_kubeconform_results,
                    "kubelinter_results": all_kubelinter_results,
                    "report": final_report,
                    "files_validated": total_processed_files
                }
                
        except Exception as e:
            error_msg = f"❌ Validation failed: {str(e)}"
            print(error_msg)
            return {
                "status": "error",
                "error": str(e),
                "kubeconform_results": [],
                "kubelinter_results": [],
                "report": error_msg
            }
    
    def validate_local_files(self, file_paths: list, 
                           output_file: Optional[str] = None) -> dict:
        """
        Validate local Kubernetes files using both kubeconform and kube-linter.
        
        Args:
            file_paths: List of file paths to validate
            output_file: Optional file to save the report
            
        Returns:
            Dictionary containing validation results and comprehensive report
        """
        print(f"🔄 Starting comprehensive validation for {len(file_paths)} local files")
        print("=" * 80)
        
        try:
            # Run kubeconform validation
            print("✅ Running kubeconform schema validation...")
            kubeconform_results = self.kubeconform.batch_validate(file_paths)
            
            # Run kube-linter analysis
            print("🔍 Running kube-linter best practices analysis...")
            kubelinter_results = self.kubelinter.batch_lint(file_paths)
            
            # Generate comprehensive AI report with fixes
            print("🤖 Generating comprehensive AI-powered report with fixes...")
            detailed_report = self.agent.generate_comprehensive_report(
                kubeconform_results, kubelinter_results, None, output_file
            )
            
            # Print summary
            self._print_comprehensive_summary(kubeconform_results, kubelinter_results)
            
            return {
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "kubeconform_results": kubeconform_results,
                "kubelinter_results": kubelinter_results,
                "report": detailed_report,
                "files_validated": len(file_paths)
            }
            
        except Exception as e:
            error_msg = f"❌ Validation failed: {str(e)}"
            print(error_msg)
            return {
                "status": "error",
                "error": str(e),
                "kubeconform_results": [],
                "kubelinter_results": [],
                "report": error_msg
            }
    
    def _print_comprehensive_summary(self, kubeconform_results: list, kubelinter_results: list):
        """Print a comprehensive summary of both validation and linting results."""
        # Get unique files
        all_files = set()
        valid_files = set()
        
        for result in kubeconform_results:
            file_path = result.get('file', '')
            all_files.add(file_path)
            if result.get('valid', False):
                valid_files.add(file_path)
        
        for result in kubelinter_results:
            file_path = result.get('file', '')
            all_files.add(file_path)
            if result.get('valid', False):
                valid_files.add(file_path)
        
        total_files = len(all_files)
        valid_file_count = len(valid_files)
        invalid_files = total_files - valid_file_count
        
        # Count errors and warnings
        validation_errors = sum(len(r.get('errors', [])) for r in kubeconform_results if not r.get('valid', True))
        
        linting_warnings = 0
        for result in kubelinter_results:
            kubelinter_output = result.get('kubelinter_output')
            if kubelinter_output:
                reports = kubelinter_output.get('Reports', [])
                if reports:
                    linting_warnings += len(reports)
        
        print(f"\n📊 Comprehensive Summary:")
        print(f"   Total files: {total_files}")
        print(f"   Valid files: {valid_file_count}")
        print(f"   Files with issues: {invalid_files}")
        print(f"   Schema validation errors: {validation_errors}")
        print(f"   Best practice warnings: {linting_warnings}")
        print(f"   Overall success rate: {(valid_file_count/total_files*100):.1f}%")
        
        # Risk assessment
        total_issues = validation_errors + linting_warnings
        risk_level = "🔴 HIGH" if total_issues > 20 else "🟡 MEDIUM" if total_issues > 5 else "🟢 LOW"
        print(f"   Risk level: {risk_level}")
    
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
        description="Comprehensive Kubernetes Validation Tool with AI-Powered Reporting"
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
    parser.add_argument(
        '--batch-size',
        type=int,
        default=10,
        help='Number of files to process in each batch for repository validation (default: 10)'
    )
    # File type selection
    parser.add_argument('--file-types', nargs='+', 
                      choices=['yaml', 'terraform', 'both'], 
                      default=['both'],
                      help='File types to analyze: yaml, terraform, or both (default: both)')
    
    # Add single batch analysis option
    parser.add_argument('--single-batch', action='store_true',
                      help='Analyze only the first batch and generate comprehensive report')
    
    # Separate reports option
    parser.add_argument('--separate-reports', action='store_true',
                      help='Generate separate reports for each file type')
    
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
    if args.repo:
        # Use command line repo URL
        repo_url = args.repo
    elif validator.repo_url:
        # Use repo URL from .env file
        repo_url = validator.repo_url
        print(f"📋 Using repository from .env: {repo_url}")
    else:
        # No repo specified anywhere
        if args.files:
            # Validate local files
            results = validator.validate_local_files(args.files, args.output)
        else:
            print("❌ Please specify either:")
            print("   --repo <repository_url>")
            print("   --files <file1> <file2> ...")
            print("   OR set REPO_URL in your .env file")
            return 1
    
    # Validate repository if we have a repo URL
    if 'repo_url' in locals():
        results = validator.validate_repository(
            repo_url=repo_url,
            branch=args.branch,
            batch_size=args.batch_size,
            output_file=args.output,
            single_batch=args.single_batch
        )
    
    # Print report to console (unless already saved)
    if not args.output:
        print("\n" + "=" * 80)
    print(results.get('report', 'No report generated'))
    
    # Save to file if requested and not already saved by agent
    if args.output and not os.path.exists(args.output):
        validator.save_report(results, args.output)
    
    # Exit with appropriate code
    if results.get('status') == 'error':
        return 1
    elif results.get('status') == 'no_files':
        return 2
    else:
        # Check if there were validation failures
        kubeconform_results = results.get('kubeconform_results', [])
        kubelinter_results = results.get('kubelinter_results', [])
        
        validation_failures = sum(1 for r in kubeconform_results if not r.get('valid', True))
        linting_issues = sum(1 for r in kubelinter_results if not r.get('valid', True))
        
        # Return 0 if no issues, 3 if there are issues but validation succeeded
        return 0 if validation_failures == 0 and linting_issues == 0 else 3


if __name__ == '__main__':
    sys.exit(main())
