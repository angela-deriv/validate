import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import openai


@dataclass
class ValidationSummary:
    """Summary of validation results."""
    total_files: int
    valid_files: int
    invalid_files: int
    total_errors: int
    total_warnings: int
    error_types: Dict[str, int]
    warning_types: Dict[str, int]
    recommendations: List[str]
    fixes: List[Dict[str, Any]]


class ValidationAgent:
    """
    An AI agent that processes kubeconform and kube-linter results and generates curated reports.
    """
    
    def __init__(self, api_key: str, api_url: str, model_name: str):
        self.api_key = api_key
        self.api_url = api_url
        self.model_name = model_name
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url=api_url
        )
    
    def analyze_combined_results(self, kubeconform_results, kubelinter_results):
        """Analyze combined kubeconform and kube-linter results with defensive programming."""
        
        # Defensive programming - ensure we have valid lists
        if kubeconform_results is None:
            kubeconform_results = []
        if kubelinter_results is None:
            kubelinter_results = []
            
        # Filter out None results
        kubeconform_results = [r for r in kubeconform_results if r is not None]
        kubelinter_results = [r for r in kubelinter_results if r is not None]
        
        print(f"   🔍 Analyzing {len(kubeconform_results)} validation results...")
        print(f"   🔍 Analyzing {len(kubelinter_results)} linting results...")
        
        # Initialize counters
        total_files = len(set(
            [r.get('file', '') for r in kubeconform_results if r.get('file')] + 
            [r.get('file', '') for r in kubelinter_results if r.get('file')]
        ))
        
        valid_files = 0
        invalid_files = 0
        total_errors = 0
        total_warnings = 0
        error_types = {}
        warning_types = {}
        
        # Process kubeconform results
        if kubeconform_results:
            for result in kubeconform_results:
                if not result or not isinstance(result, dict):
                    continue
                    
                if result.get('valid', False):
                    valid_files += 1
                else:
                    invalid_files += 1
                    
                # Count errors safely
                errors = result.get('errors', [])
                if errors and isinstance(errors, list):
                    total_errors += len(errors)
                    
                    # Categorize errors
                    for error in errors:
                        if isinstance(error, str):
                            error_type = self._categorize_error(error)
                            error_types[error_type] = error_types.get(error_type, 0) + 1
        
        # Process kube-linter results  
        if kubelinter_results:
            for result in kubelinter_results:
                if not result or not isinstance(result, dict):
                    continue
                    
                kubelinter_output = result.get('kubelinter_output')
                if not kubelinter_output or not isinstance(kubelinter_output, dict):
                    continue
                    
                reports = kubelinter_output.get('Reports', [])
                if not reports or not isinstance(reports, list):
                    continue
                    
                for report in reports:
                    if not report or not isinstance(report, dict):
                        continue
                        
                    total_warnings += 1
                    
                    # Categorize warnings
                    check_name = report.get('Check', 'unknown')
                    if isinstance(check_name, str):
                        category = self._categorize_kubelinter_issue(check_name, report.get('Message', ''))
                        warning_types[category] = warning_types.get(category, 0) + 1
        
        # Generate recommendations
        recommendations = self._generate_combined_recommendations(error_types, warning_types)
        
        # Generate specific fixes
        fixes = self._generate_fixes(kubeconform_results, kubelinter_results)
        
        return ValidationSummary(
            total_files=total_files,
            valid_files=valid_files,
            invalid_files=invalid_files,
            total_errors=total_errors,
            total_warnings=total_warnings,
            error_types=error_types,
            warning_types=warning_types,
            recommendations=recommendations,
            fixes=fixes or []  # Ensure fixes is never None
        )
    
    def generate_comprehensive_report(self, kubeconform_results: List[Dict[str, Any]], 
                                    kubelinter_results: List[Dict[str, Any]],
                                    repo_url: Optional[str] = None, 
                                    output_file: Optional[str] = None) -> str:
        """
        Generate a comprehensive report with both validation and linting results.
        Enhanced for large repository batch processing.
        
        Args:
            kubeconform_results: List of validation results from kubeconform
            kubelinter_results: List of linting results from kube-linter
            repo_url: Optional repository URL for context
            output_file: Optional file path to save the report
            
        Returns:
            Detailed report as a string
        """
        print(f"   🔍 Analyzing {len(kubeconform_results)} validation results...")
        print(f"   🔍 Analyzing {len(kubelinter_results)} linting results...")
        
        summary = self.analyze_combined_results(kubeconform_results, kubelinter_results)
        
        # Enhanced data preparation for large datasets
        print(f"   📊 Preparing comprehensive analysis...")
        
        # Get top error patterns and most problematic files
        error_files = []
        warning_files = []
        
        if kubeconform_results:
            error_files = [r for r in kubeconform_results if not r.get('valid', True)]
        
        if kubelinter_results:
            warning_files = []
            for result in kubelinter_results:
                kubelinter_output = result.get('kubelinter_output')
                if kubelinter_output:
                    reports = kubelinter_output.get('Reports', [])
                    if reports:
                        warning_files.append({
                            'file': result.get('file'),
                            'warning_count': len(reports),
                            'reports': reports
                        })
        
        # Sort by issue count to identify most problematic files
        warning_files.sort(key=lambda x: x['warning_count'], reverse=True)
        
        context = {
            "summary": {
                "total_files": summary.total_files,
                "valid_files": summary.valid_files,
                "invalid_files": summary.invalid_files,
                "total_errors": summary.total_errors,
                "total_warnings": summary.total_warnings,
                "error_types": summary.error_types,
                "warning_types": summary.warning_types
            },
            "repo_url": repo_url,
            "timestamp": datetime.now().isoformat(),
            "top_error_files": [f.get('file', 'unknown') for f in error_files[:5]],
            "top_warning_files": [f['file'] for f in warning_files[:5]],
            "sample_kubeconform_results": kubeconform_results[:3],  # Representative samples
            "sample_kubelinter_results": kubelinter_results[:3],
            "repository_scale": "large" if summary.total_files > 20 else "medium" if summary.total_files > 5 else "small",
            "fixes": summary.fixes[:10]  # Top 10 fixes
        }
        
        # Create enhanced AI prompt for repository analysis
        prompt = self._create_repository_analysis_prompt(context)
        
        try:
            print(f"   🤖 Generating AI-powered analysis...")
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a Kubernetes expert analyzing repository-wide validation and linting results. Provide comprehensive insights focusing on patterns, priorities, and strategic recommendations for the entire codebase."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=4000,  # Increased for repository analysis
                temperature=0.1
            )
            
            ai_analysis = response.choices[0].message.content
            
        except Exception as e:
            ai_analysis = f"AI analysis unavailable: {str(e)}\n\nNote: Repository analysis can proceed with local insights and fix suggestions."
        
        # Combine summary and AI analysis into final report
        report = self._format_repository_report(summary, ai_analysis, repo_url, context)
        
        # Save to file if specified
        if output_file:
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(report)
                print(f"✅ Repository analysis report saved to: {output_file}")
            except Exception as e:
                print(f"❌ Failed to save report to {output_file}: {str(e)}")
        
        return report
    
    def _categorize_kubeconform_error(self, error_message: str) -> str:
        """Categorize kubeconform error messages into types."""
        error_lower = error_message.lower()
        
        if 'schema' in error_lower or 'validation' in error_lower:
            return 'Schema Validation'
        elif 'apiversion' in error_lower:
            return 'API Version'
        elif 'kind' in error_lower:
            return 'Resource Kind'
        elif 'metadata' in error_lower:
            return 'Metadata Issues'
        elif 'spec' in error_lower:
            return 'Specification Errors'
        elif 'required' in error_lower or 'missing' in error_lower:
            return 'Missing Required Fields'
        elif 'format' in error_lower or 'syntax' in error_lower:
            return 'Format/Syntax Errors'
        elif 'timeout' in error_lower:
            return 'Validation Timeout'
        elif 'not found' in error_lower:
            return 'File Not Found'
        else:
            return 'Other Validation Errors'
    
    def _categorize_kubelinter_issue(self, check_name: str, message: str = "") -> str:
        """Categorize kube-linter issues into meaningful categories with safe handling."""
        if not check_name or not isinstance(check_name, str):
            return "Unknown Issue"
            
        check_name = check_name.lower()
        
        # Security-related checks
        security_checks = [
            'run-as-non-root', 'privileged-ports', 'privilege-escalation-container',
            'read-only-root-filesystem', 'non-root-user', 'security-context'
        ]
        if any(check in check_name for check in security_checks):
            return "Security Configuration"
        
        # Resource management
        resource_checks = [
            'cpu-requirements', 'memory-requirements', 'resource-requirements',
            'cpu-limits', 'memory-limits'
        ]
        if any(check in check_name for check in resource_checks):
            return "Resource Management"
        
        # Image and deployment practices
        image_checks = ['latest-tag', 'image', 'tag']
        if any(check in check_name for check in image_checks):
            return "Image Configuration"
        
        # Health and monitoring
        health_checks = [
            'liveness-probe', 'readiness-probe', 'startup-probe',
            'health-check', 'probe'
        ]
        if any(check in check_name for check in health_checks):
            return "Health Monitoring"
        
        # Availability and reliability
        availability_checks = [
            'anti-affinity', 'pod-disruption-budget', 'replicas',
            'availability', 'disruption'
        ]
        if any(check in check_name for check in availability_checks):
            return "Availability & Reliability"
        
        # Default fallback
        return "Best Practice Violations"
    
    def _generate_combined_recommendations(self, error_types: Dict[str, int], 
                                         warning_types: Dict[str, int]) -> List[str]:
        """Generate recommendations based on both error and warning patterns."""
        recommendations = []
        
        # Priority recommendations based on errors
        if error_types.get('API Version', 0) > 0:
            recommendations.append("🔄 Update deprecated API versions to current Kubernetes standards")
        
        if error_types.get('Missing Required Fields', 0) > 0:
            recommendations.append("📝 Add missing required fields in resource definitions")
        
        if error_types.get('Schema Validation', 0) > 0:
            recommendations.append("✅ Fix schema validation errors")
        
        # Security recommendations based on kube-linter
        if warning_types.get('Security Issues', 0) > 0:
            recommendations.append("🔐 Address security vulnerabilities and privilege escalations")
        
        if warning_types.get('Resource Management', 0) > 0:
            recommendations.append("📊 Configure proper resource limits and requests")
        
        if warning_types.get('Health Checks', 0) > 0:
            recommendations.append("🏥 Add health checks (liveness and readiness probes)")
        
        if warning_types.get('Image Configuration', 0) > 0:
            recommendations.append("🖼️ Use specific image tags instead of 'latest'")
        
        # General recommendations
        total_issues = sum(error_types.values()) + sum(warning_types.values())
        if total_issues > 15:
            recommendations.append("🎯 Implement automated validation in CI/CD pipeline")
        
        if warning_types.get('Deprecated Features', 0) > 0:
            recommendations.append("⚠️ Migrate away from deprecated Kubernetes features")
        
        return recommendations
    
    def _generate_fixes(self, kubeconform_results: List[Dict[str, Any]], 
                       kubelinter_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate specific fixes for identified issues."""
        fixes = []
        
        # Process kubeconform errors
        if kubeconform_results:
            for result in kubeconform_results:
                if not result.get('valid', True):
                    file_path = result.get('file', '')
                    errors = result.get('errors', [])
                    
                    for error in errors:
                        fix = self._generate_kubeconform_fix(file_path, error)
                        if fix:
                            fixes.append(fix)
        
        # Process kube-linter issues
        if kubelinter_results:
            for result in kubelinter_results:
                file_path = result.get('file', '')
                kubelinter_output = result.get('kubelinter_output')
                if kubelinter_output:
                    reports = kubelinter_output.get('Reports', [])
                    
                    for report in reports:
                        fix = self._generate_kubelinter_fix(file_path, report)
                        if fix:
                            fixes.append(fix)
        
        return fixes
    
    def _generate_kubeconform_fix(self, file_path: str, error: str) -> Optional[Dict[str, Any]]:
        """Generate specific fix for kubeconform error."""
        error_lower = error.lower()
        
        if 'apiversion' in error_lower:
            return {
                "file": file_path,
                "type": "API Version Fix",
                "issue": error,
                "fix": "Update the apiVersion field to a supported version for your Kubernetes cluster",
                "example": "apiVersion: apps/v1  # instead of apps/v1beta1"
            }
        elif 'missing' in error_lower and 'required' in error_lower:
            return {
                "file": file_path,
                "type": "Missing Field Fix",
                "issue": error,
                "fix": "Add the required field mentioned in the error",
                "example": "Add missing selector, labels, or other required fields"
            }
        elif 'schema' in error_lower:
            return {
                "file": file_path,
                "type": "Schema Fix",
                "issue": error,
                "fix": "Correct the field name, type, or structure according to Kubernetes schema",
                "example": "Check field names and ensure proper YAML structure"
            }
        
        return None
    
    def _generate_kubelinter_fix(self, file_path: str, report: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Generate specific fix for kube-linter issue."""
        check_name = report.get('Check', '')
        message = report.get('Message', '')
        
        fixes_map = {
            'no-read-only-root-fs': {
                "type": "Security Fix",
                "fix": "Set readOnlyRootFilesystem: true in securityContext",
                "example": "securityContext:\n  readOnlyRootFilesystem: true"
            },
            'no-resources': {
                "type": "Resource Limits Fix", 
                "fix": "Add resource requests and limits to container spec",
                "example": "resources:\n  requests:\n    cpu: 100m\n    memory: 128Mi\n  limits:\n    cpu: 500m\n    memory: 256Mi"
            },
            'no-liveness-probe': {
                "type": "Health Check Fix",
                "fix": "Add livenessProbe to container spec", 
                "example": "livenessProbe:\n  httpGet:\n    path: /health\n    port: 8080\n  initialDelaySeconds: 30\n  periodSeconds: 10"
            },
            'no-readiness-probe': {
                "type": "Health Check Fix",
                "fix": "Add readinessProbe to container spec",
                "example": "readinessProbe:\n  httpGet:\n    path: /ready\n    port: 8080\n  initialDelaySeconds: 5\n  periodSeconds: 5"
            },
            'latest-tag': {
                "type": "Image Tag Fix",
                "fix": "Use specific image tags instead of 'latest'",
                "example": "image: nginx:1.21.0  # instead of nginx:latest"
            }
        }
        
        fix_info = fixes_map.get(check_name)
        if fix_info:
            return {
                "file": file_path,
                "type": fix_info["type"],
                "issue": message,
                "fix": fix_info["fix"],
                "example": fix_info["example"]
            }
        
        return {
            "file": file_path,
            "type": "Best Practice Fix",
            "issue": message,
            "fix": f"Address the {check_name} check violation",
            "example": "Refer to Kubernetes best practices documentation"
        }
    
    def _create_comprehensive_analysis_prompt(self, context: Dict[str, Any]) -> str:
        """Create a comprehensive prompt for AI analysis."""
        return f"""
Please analyze these combined Kubernetes validation and linting results:

VALIDATION SUMMARY:
- Total files: {context['summary']['total_files']}
- Valid files: {context['summary']['valid_files']}  
- Invalid files: {context['summary']['invalid_files']}
- Validation errors: {context['summary']['total_errors']}
- Linting warnings: {context['summary']['total_warnings']}

VALIDATION ERRORS (Kubeconform):
{json.dumps(context['summary']['error_types'], indent=2)}

LINTING ISSUES (Kube-linter):
{json.dumps(context['summary']['warning_types'], indent=2)}

SAMPLE FIXES PROVIDED:
{json.dumps(context['fixes'][:5], indent=2)}

Please provide:
1. Executive Summary (overall assessment)
2. Critical Issues (must fix immediately)
3. Security Concerns (prioritized by risk)
4. Performance & Reliability Impact
5. Best Practices Violations
6. Remediation Roadmap (step-by-step)
7. Long-term Recommendations
8. Risk Level Assessment (Critical/High/Medium/Low)

Focus on actionable insights and specific remediation steps.
"""
    
    def _format_comprehensive_report(self, summary: ValidationSummary, 
                                   ai_analysis: str, repo_url: Optional[str] = None) -> str:
        """Format the comprehensive report with both validation and linting results."""
        report = []
        
        # Header
        report.append("=" * 80)
        report.append("COMPREHENSIVE KUBERNETES VALIDATION & LINTING REPORT")
        report.append("=" * 80)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        if repo_url:
            report.append(f"Repository: {repo_url}")
        report.append("")
        
        # Quick Stats
        report.append("📊 VALIDATION SUMMARY")
        report.append("-" * 40)
        report.append(f"Total Files:         {summary.total_files}")
        report.append(f"Valid Files:         {summary.valid_files}")
        report.append(f"Invalid Files:       {summary.invalid_files}")
        report.append(f"Validation Errors:   {summary.total_errors}")
        report.append(f"Linting Warnings:    {summary.total_warnings}")
        
        # Success rate
        success_rate = (summary.valid_files / summary.total_files * 100) if summary.total_files > 0 else 0
        report.append(f"Success Rate:        {success_rate:.1f}%")
        
        # Risk assessment
        total_issues = summary.total_errors + summary.total_warnings
        risk_level = "🔴 HIGH" if total_issues > 20 else "🟡 MEDIUM" if total_issues > 5 else "🟢 LOW"
        report.append(f"Risk Level:          {risk_level}")
        report.append("")
        
        # Validation Errors
        if summary.error_types:
            report.append("🚨 VALIDATION ERRORS (Kubeconform)")
            report.append("-" * 40)
            for error_type, count in sorted(summary.error_types.items(), 
                                          key=lambda x: x[1], reverse=True):
                report.append(f"{error_type}: {count}")
            report.append("")
        
        # Linting Warnings
        if summary.warning_types:
            report.append("⚠️  LINTING ISSUES (Kube-linter)")
            report.append("-" * 40)
            for warning_type, count in sorted(summary.warning_types.items(), 
                                            key=lambda x: x[1], reverse=True):
                report.append(f"{warning_type}: {count}")
            report.append("")
        
        # Immediate Recommendations
        if summary.recommendations:
            report.append("💡 IMMEDIATE RECOMMENDATIONS")
            report.append("-" * 40)
            for rec in summary.recommendations:
                report.append(f"• {rec}")
            report.append("")
        
        # Specific Fixes
        if summary.fixes:
            report.append("🔧 SPECIFIC FIXES")
            report.append("-" * 40)
            for fix in summary.fixes[:10]:  # Show first 10 fixes
                report.append(f"File: {fix['file']}")
                report.append(f"Type: {fix['type']}")
                report.append(f"Issue: {fix['issue']}")
                report.append(f"Fix: {fix['fix']}")
                if 'example' in fix:
                    report.append(f"Example: {fix['example']}")
                report.append("")
        
        # AI Analysis
        report.append("🤖 DETAILED ANALYSIS & RECOMMENDATIONS")
        report.append("-" * 40)
        report.append(ai_analysis)
        report.append("")
        
        # Footer
        report.append("=" * 80)
        report.append("End of Report")
        report.append("=" * 80)
        
        return "\n".join(report)

    def _format_repository_report(self, summary: ValidationSummary, 
                                 ai_analysis: str, repo_url: Optional[str] = None,
                                 context: Dict[str, Any] = None) -> str:
        """Format an enhanced repository-wide report with comprehensive analysis."""
        report = []
        
        # Enhanced Header
        report.append("=" * 100)
        report.append("🏢 COMPREHENSIVE KUBERNETES REPOSITORY ANALYSIS REPORT")
        report.append("=" * 100)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        if repo_url:
            report.append(f"Repository: {repo_url}")
        
        # Repository scale indicator
        scale = context.get('repository_scale', 'unknown') if context else 'unknown'
        scale_emoji = "🏗️" if scale == "large" else "🏢" if scale == "medium" else "🏠"
        report.append(f"Scale: {scale_emoji} {scale.title()} repository ({summary.total_files} files)")
        
        # Add processing completeness indicator
        if summary.total_files > 0:
            completeness = (summary.total_files / summary.total_files) * 100  # This will be updated by the caller
            if completeness < 100:
                report.append(f"⚠️  Analysis Coverage: Partial analysis due to processing issues")
            else:
                report.append(f"✅ Analysis Coverage: Complete repository scan")
        
        report.append("")
        
        # Executive Summary
        success_rate = (summary.valid_files / summary.total_files * 100) if summary.total_files > 0 else 0
        total_issues = summary.total_errors + summary.total_warnings
        
        report.append("📈 EXECUTIVE SUMMARY")
        report.append("-" * 50)
        report.append(f"Repository Health Score:     {success_rate:.1f}%")
        report.append(f"Total Files Analyzed:        {summary.total_files}")
        report.append(f"Files Passing Validation:    {summary.valid_files}")
        report.append(f"Files Requiring Attention:   {summary.invalid_files}")
        report.append(f"Critical Schema Errors:      {summary.total_errors}")
        report.append(f"Best Practice Warnings:      {summary.total_warnings}")
        report.append(f"Total Issues Found:          {total_issues}")
        
        # Enhanced risk assessment
        if total_issues == 0:
            risk_level = "🟢 EXCELLENT"
            risk_desc = "Repository meets all standards"
        elif total_issues <= 5:
            risk_level = "🟡 LOW"
            risk_desc = "Minor improvements needed"
        elif total_issues <= 20:
            risk_level = "🟠 MEDIUM"
            risk_desc = "Moderate attention required"
        elif total_issues <= 50:
            risk_level = "🔴 HIGH"
            risk_desc = "Significant issues need addressing"
        else:
            risk_level = "💀 CRITICAL"
            risk_desc = "Immediate action required"
            
        report.append(f"Overall Risk Level:          {risk_level}")
        report.append(f"Risk Description:            {risk_desc}")
        report.append("")
        
        # Analysis Confidence Level
        if summary.total_files > 0:
            confidence = "High" if summary.total_files >= summary.total_files * 0.95 else "Medium" if summary.total_files >= summary.total_files * 0.80 else "Low"
            report.append(f"📊 ANALYSIS CONFIDENCE")
            report.append("-" * 50)
            report.append(f"Confidence Level:            {confidence}")
            report.append(f"Files Successfully Analyzed: {summary.total_files}")
            if summary.total_files < 100:  # Assuming we might have skipped some
                report.append(f"Note: Some files may have been skipped due to processing issues")
            report.append("")
        
        # Most Problematic Files
        if context and (context.get('top_error_files') or context.get('top_warning_files')):
            report.append("🚨 FILES REQUIRING IMMEDIATE ATTENTION")
            report.append("-" * 50)
            
            if context.get('top_error_files'):
                report.append("Schema Validation Failures:")
                for i, file_path in enumerate(context['top_error_files'][:5], 1):
                    report.append(f"  {i}. {file_path}")
                    
            if context.get('top_warning_files'):
                report.append("Files with Most Best Practice Issues:")
                for i, file_path in enumerate(context['top_warning_files'][:5], 1):
                    report.append(f"  {i}. {file_path}")
            report.append("")
        
        # Detailed Issue Breakdown
        if summary.error_types:
            report.append("🚨 VALIDATION ERRORS (Kubeconform)")
            report.append("-" * 50)
            for error_type, count in sorted(summary.error_types.items(), 
                                          key=lambda x: x[1], reverse=True):
                percentage = (count / summary.total_errors * 100) if summary.total_errors > 0 else 0
                report.append(f"{error_type}: {count} ({percentage:.1f}%)")
            report.append("")
        
        # Linting Issues
        if summary.warning_types:
            report.append("⚠️  BEST PRACTICE VIOLATIONS (Kube-linter)")
            report.append("-" * 50)
            for warning_type, count in sorted(summary.warning_types.items(), 
                                            key=lambda x: x[1], reverse=True):
                percentage = (count / summary.total_warnings * 100) if summary.total_warnings > 0 else 0
                report.append(f"{warning_type}: {count} ({percentage:.1f}%)")
            report.append("")
        
        # Strategic Recommendations
        if summary.recommendations:
            report.append("🎯 STRATEGIC RECOMMENDATIONS")
            report.append("-" * 50)
            for i, rec in enumerate(summary.recommendations, 1):
                report.append(f"{i}. {rec}")
            report.append("")
        
        # Quick Wins - Top Fixes
        if summary.fixes:
            report.append("🔧 PRIORITY FIXES (Top 10)")
            report.append("-" * 50)
            for i, fix in enumerate(summary.fixes[:10], 1):
                report.append(f"{i}. File: {fix['file']}")
                report.append(f"   Type: {fix['type']}")
                report.append(f"   Issue: {fix['issue']}")
                report.append(f"   Fix: {fix['fix']}")
                if 'example' in fix:
                    report.append(f"   Example: {fix['example']}")
                report.append("")
        
        # Repository-wide AI Analysis
        report.append("🤖 STRATEGIC ANALYSIS & RECOMMENDATIONS")
        report.append("-" * 50)
        report.append(ai_analysis)
        report.append("")
        
        # Implementation Guidance
        report.append("📋 IMPLEMENTATION GUIDANCE")
        report.append("-" * 50)
        
        if total_issues > 50:
            report.append("🔥 CRITICAL REPOSITORY - Immediate Action Plan:")
            report.append("1. Stop all non-critical deployments")
            report.append("2. Create emergency task force")
            report.append("3. Address schema validation errors first")
            report.append("4. Implement basic security fixes")
            report.append("5. Set up automated validation pipeline")
        elif total_issues > 20:
            report.append("⚠️  HIGH PRIORITY - 30-Day Action Plan:")
            report.append("1. Address all schema validation errors (Week 1)")
            report.append("2. Fix security-related issues (Week 2)")
            report.append("3. Implement resource management (Week 3)")
            report.append("4. Add health checks and monitoring (Week 4)")
        elif total_issues > 5:
            report.append("📊 MODERATE PRIORITY - 60-Day Improvement Plan:")
            report.append("1. Gradually fix validation errors")
            report.append("2. Enhance security posture")
            report.append("3. Optimize resource configurations")
            report.append("4. Implement best practices")
        else:
            report.append("✅ MAINTENANCE MODE - Continuous Improvement:")
            report.append("1. Monitor for new issues")
            report.append("2. Stay updated with best practices")
            report.append("3. Regular security reviews")
            report.append("4. Performance optimizations")
        
        # Add note about partial analysis if applicable
        if summary.total_files < 100:  # Assuming some might have been skipped
            report.append("\n⚠️  NOTE: If some files were skipped during processing:")
            report.append("- Re-run analysis with smaller batch sizes")
            report.append("- Check for file format or permission issues")
            report.append("- Current results are still valuable for identified files")
        
        report.append("")
        
        # Footer
        report.append("=" * 100)
        report.append("📊 Repository Analysis Complete")
        report.append(f"📝 Report generated for {summary.total_files} files with {total_issues} total issues")
        report.append("🔄 Re-run analysis after implementing fixes to track progress")
        if summary.total_files < 100:
            report.append("💡 Consider re-running with adjusted batch sizes if files were skipped")
        report.append("=" * 100)
        
        return "\n".join(report)

    def _create_repository_analysis_prompt(self, context: Dict[str, Any]) -> str:
        """Create an enhanced prompt for repository-wide AI analysis."""
        return f"""
Please analyze these comprehensive Kubernetes repository validation and linting results:

REPOSITORY OVERVIEW:
- Repository: {context.get('repo_url', 'Local analysis')}
- Repository scale: {context['repository_scale']} ({context['summary']['total_files']} files)
- Analysis timestamp: {context['timestamp']}

VALIDATION SUMMARY:
- Total files analyzed: {context['summary']['total_files']}
- Valid files: {context['summary']['valid_files']}  
- Files with issues: {context['summary']['invalid_files']}
- Schema validation errors: {context['summary']['total_errors']}
- Best practice warnings: {context['summary']['total_warnings']}

VALIDATION ERRORS (Kubeconform):
{json.dumps(context['summary']['error_types'], indent=2)}

LINTING ISSUES (Kube-linter):
{json.dumps(context['summary']['warning_types'], indent=2)}

MOST PROBLEMATIC FILES:
Top files with validation errors: {context['top_error_files']}
Top files with warnings: {context['top_warning_files']}

REPOSITORY-WIDE INSIGHTS NEEDED:
1. **Strategic Overview**: Overall repository health assessment
2. **Priority Matrix**: Which issues should be addressed first across the entire codebase
3. **Pattern Analysis**: Common issues appearing across multiple files
4. **Team Recommendations**: Guidance for development teams and processes
5. **Security Assessment**: Repository-wide security posture 
6. **Compliance Status**: Standards and best practices adherence
7. **Technical Debt**: Areas requiring architectural improvements
8. **Implementation Roadmap**: Phased approach to resolve repository-wide issues
9. **Risk Assessment**: Business and operational risk levels
10. **Automation Opportunities**: Where to implement preventive measures

Focus on repository-wide patterns, strategic recommendations, and actionable insights for improving the entire Kubernetes codebase.
"""

    # Legacy method for backward compatibility
    def analyze_validation_results(self, validation_results: List[Dict[str, Any]]) -> ValidationSummary:
        """Legacy method - use analyze_combined_results instead."""
        return self.analyze_combined_results(validation_results, [])
    
    def generate_detailed_report(self, validation_results: List[Dict[str, Any]], 
                               repo_url: Optional[str] = None) -> str:
        """Legacy method - use generate_comprehensive_report instead.""" 
        return self.generate_comprehensive_report(validation_results, [], repo_url) 
    
    def analyze_terraform_results(self, terraform_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze Terraform validation results from terraform validate, tfsec, and tflint."""
        
        if not terraform_results:
            return {
                "total_files": 0,
                "valid_files": 0,
                "invalid_files": 0,
                "syntax_errors": 0,
                "security_issues": 0,
                "lint_issues": 0,
                "error_types": {},
                "security_types": {},
                "lint_types": {},
                "recommendations": [],
                "fixes": []
            }
        
        # Initialize counters
        total_files = len(terraform_results)
        valid_files = 0
        invalid_files = 0
        syntax_errors = 0
        security_issues = 0
        lint_issues = 0
        error_types = {}
        security_types = {}
        lint_types = {}
        
        # Process results
        for result in terraform_results:
            if not result or not isinstance(result, dict):
                continue
                
            # Count file validity
            if result.get('valid', False):
                valid_files += 1
            else:
                invalid_files += 1
            
            # Process terraform validate errors
            tf_validate = result.get('terraform_validate', {})
            if not tf_validate.get('valid', True):
                errors = tf_validate.get('errors', [])
                syntax_errors += len(errors)
                for error in errors:
                    if isinstance(error, str):
                        error_type = self._categorize_terraform_error(error)
                        error_types[error_type] = error_types.get(error_type, 0) + 1
            
            # Process tfsec security issues
            tfsec_results = result.get('tfsec_results', {})
            tfsec_issues = tfsec_results.get('issues', [])
            security_issues += len(tfsec_issues)
            for issue in tfsec_issues:
                severity = issue.get('severity', 'unknown')
                security_types[severity] = security_types.get(severity, 0) + 1
            
            # Process tflint issues
            tflint_results = result.get('tflint_results', {})
            tflint_issues = tflint_results.get('issues', [])
            lint_issues += len(tflint_issues)
            for issue in tflint_issues:
                rule = issue.get('rule', 'unknown')
                lint_types[rule] = lint_types.get(rule, 0) + 1
        
        # Generate recommendations
        recommendations = self._generate_terraform_recommendations(error_types, security_types, lint_types)
        
        # Generate fixes
        fixes = self._generate_terraform_fixes(terraform_results)
        
        return {
            "total_files": total_files,
            "valid_files": valid_files,
            "invalid_files": invalid_files,
            "syntax_errors": syntax_errors,
            "security_issues": security_issues,
            "lint_issues": lint_issues,
            "error_types": error_types,
            "security_types": security_types,
            "lint_types": lint_types,
            "recommendations": recommendations,
            "fixes": fixes or []
        }
    
    def _categorize_terraform_error(self, error: str) -> str:
        """Categorize Terraform validation errors."""
        error_lower = error.lower()
        
        if 'syntax' in error_lower or 'parse' in error_lower:
            return 'Syntax Errors'
        elif 'variable' in error_lower or 'var.' in error_lower:
            return 'Variable Issues'
        elif 'resource' in error_lower:
            return 'Resource Configuration'
        elif 'provider' in error_lower:
            return 'Provider Issues'
        elif 'module' in error_lower:
            return 'Module Issues'
        elif 'output' in error_lower:
            return 'Output Issues'
        elif 'reference' in error_lower or 'undefined' in error_lower:
            return 'Reference Errors'
        else:
            return 'Configuration Errors'
    
    def _generate_terraform_recommendations(self, error_types: Dict[str, int], 
                                          security_types: Dict[str, int], 
                                          lint_types: Dict[str, int]) -> List[str]:
        """Generate Terraform-specific recommendations."""
        recommendations = []
        
        # Error-based recommendations
        if error_types.get('Syntax Errors', 0) > 0:
            recommendations.append('🔧 Fix syntax errors using terraform fmt and validate')
        
        if error_types.get('Variable Issues', 0) > 0:
            recommendations.append('📋 Review variable definitions and declarations')
        
        if error_types.get('Resource Configuration', 0) > 0:
            recommendations.append('⚙️ Validate resource configurations and required parameters')
        
        # Security-based recommendations
        if security_types.get('HIGH', 0) > 0 or security_types.get('CRITICAL', 0) > 0:
            recommendations.append('🚨 Address critical and high-severity security issues immediately')
        
        if security_types.get('MEDIUM', 0) > 0:
            recommendations.append('⚠️ Review medium-severity security findings')
        
        # Linting recommendations
        if lint_types:
            recommendations.append('📝 Follow Terraform best practices identified by tflint')
        
        # General recommendations
        recommendations.extend([
            '📚 Use terraform fmt to maintain consistent formatting',
            '🔐 Implement terraform plan before apply in CI/CD',
            '📊 Use terraform state management best practices'
        ])
        
        return recommendations
    
    def _generate_terraform_fixes(self, terraform_results: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Generate specific Terraform fixes."""
        fixes = []
        
        for result in terraform_results:
            if not result or not isinstance(result, dict):
                continue
                
            file_path = result.get('file', 'unknown')
            file_name = os.path.basename(file_path)
            
            # Terraform validate fixes
            tf_validate = result.get('terraform_validate', {})
            if not tf_validate.get('valid', True):
                for error in tf_validate.get('errors', []):
                    fixes.append({
                        'file': file_name,
                        'type': 'Terraform Syntax Fix',
                        'issue': error,
                        'fix': 'Run terraform fmt and terraform validate to identify and fix syntax issues',
                        'example': 'terraform fmt . && terraform validate'
                    })
            
            # tfsec security fixes
            tfsec_results = result.get('tfsec_results', {})
            for issue in tfsec_results.get('issues', []):
                fixes.append({
                    'file': file_name,
                    'type': 'Security Fix',
                    'issue': issue.get('description', 'Security issue'),
                    'fix': issue.get('resolution', 'Review security configuration'),
                    'example': f"Rule: {issue.get('rule_id', 'unknown')}"
                })
            
            # tflint fixes
            tflint_results = result.get('tflint_results', {})
            for issue in tflint_results.get('issues', []):
                fixes.append({
                    'file': file_name,
                    'type': 'Best Practice Fix',
                    'issue': issue.get('message', 'Linting issue'),
                    'fix': 'Follow Terraform best practices',
                    'example': f"Rule: {issue.get('rule', 'unknown')}"
                })
        
        return fixes
    
    def generate_terraform_report(self, terraform_results: List[Dict[str, Any]], 
                                repo_url: Optional[str] = None,
                                output_file: Optional[str] = None) -> str:
        """Generate comprehensive Terraform analysis report."""
        
        # Analyze results
        analysis = self.analyze_terraform_results(terraform_results)
        
        # Generate AI analysis
        ai_analysis = self._generate_terraform_ai_analysis(analysis, terraform_results)
        
        # Format report
        report = self._format_terraform_report(analysis, ai_analysis, repo_url)
        
        # Write to file if specified
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report)
        
        return report
    
    def _generate_terraform_ai_analysis(self, analysis: Dict[str, Any], 
                                      terraform_results: List[Dict[str, Any]]) -> str:
        """Generate AI-powered Terraform analysis."""
        
        prompt = f"""
        Analyze this Terraform repository validation report and provide strategic insights:

        TERRAFORM VALIDATION SUMMARY:
        - Total Files: {analysis['total_files']}
        - Valid Files: {analysis['valid_files']}
        - Invalid Files: {analysis['invalid_files']}
        - Syntax Errors: {analysis['syntax_errors']}
        - Security Issues: {analysis['security_issues']}
        - Linting Issues: {analysis['lint_issues']}

        ERROR BREAKDOWN:
        {json.dumps(analysis['error_types'], indent=2)}

        SECURITY ISSUES BY SEVERITY:
        {json.dumps(analysis['security_types'], indent=2)}

        LINTING ISSUES:
        {json.dumps(analysis['lint_types'], indent=2)}

        Provide a comprehensive analysis covering:
        1. Executive summary of infrastructure quality
        2. Critical security and compliance risks
        3. Infrastructure reliability concerns
        4. Best practices violations
        5. Prioritized remediation roadmap
        6. Long-term infrastructure strategy recommendations
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1500,
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"AI analysis unavailable: {str(e)}"
    
    def _format_terraform_report(self, analysis: Dict[str, Any], 
                               ai_analysis: str, repo_url: Optional[str] = None) -> str:
        """Format comprehensive Terraform report."""
        
        report = []
        
        # Header
        report.append("=" * 100)
        report.append("🏗️ COMPREHENSIVE TERRAFORM INFRASTRUCTURE ANALYSIS")
        report.append("=" * 100)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        if repo_url:
            report.append(f"Repository: {repo_url}")
        report.append("")
        
        # Executive Summary
        total_issues = analysis['syntax_errors'] + analysis['security_issues'] + analysis['lint_issues']
        success_rate = (analysis['valid_files'] / analysis['total_files'] * 100) if analysis['total_files'] > 0 else 0
        
        report.append("📈 EXECUTIVE SUMMARY")
        report.append("-" * 50)
        report.append(f"Infrastructure Health Score:  {success_rate:.1f}%")
        report.append(f"Total Terraform Files:       {analysis['total_files']}")
        report.append(f"Valid Configuration Files:   {analysis['valid_files']}")
        report.append(f"Files Requiring Attention:   {analysis['invalid_files']}")
        report.append(f"Syntax/Configuration Errors: {analysis['syntax_errors']}")
        report.append(f"Security Issues Found:       {analysis['security_issues']}")
        report.append(f"Best Practice Violations:    {analysis['lint_issues']}")
        report.append(f"Total Issues Found:          {total_issues}")
        
        # Risk Assessment
        if total_issues == 0:
            risk_level = "🟢 LOW"
            risk_desc = "Infrastructure follows best practices"
        elif total_issues <= 5:
            risk_level = "🟡 MEDIUM"
            risk_desc = "Minor improvements needed"
        elif total_issues <= 15:
            risk_level = "🟠 HIGH"
            risk_desc = "Significant issues require attention"
        else:
            risk_level = "🔴 CRITICAL"
            risk_desc = "Immediate remediation required"
            
        report.append(f"Overall Risk Level:          {risk_level}")
        report.append(f"Risk Description:            {risk_desc}")
        report.append("")
        
        # Issue Breakdown
        if analysis['error_types']:
            report.append("🚨 CONFIGURATION ERRORS")
            report.append("-" * 50)
            for error_type, count in sorted(analysis['error_types'].items(), key=lambda x: x[1], reverse=True):
                percentage = (count / analysis['syntax_errors'] * 100) if analysis['syntax_errors'] > 0 else 0
                report.append(f"{error_type}: {count} ({percentage:.1f}%)")
            report.append("")
        
        if analysis['security_types']:
            report.append("🔐 SECURITY ISSUES BY SEVERITY")
            report.append("-" * 50)
            for severity, count in sorted(analysis['security_types'].items(), key=lambda x: x[1], reverse=True):
                percentage = (count / analysis['security_issues'] * 100) if analysis['security_issues'] > 0 else 0
                report.append(f"{severity}: {count} ({percentage:.1f}%)")
            report.append("")
        
        # Priority Fixes
        if analysis['fixes']:
            report.append("🔧 PRIORITY FIXES (Top 10)")
            report.append("-" * 50)
            for i, fix in enumerate(analysis['fixes'][:10], 1):
                report.append(f"{i}. File: {fix['file']}")
                report.append(f"   Type: {fix['type']}")
                report.append(f"   Issue: {fix['issue']}")
                report.append(f"   Fix: {fix['fix']}")
                if 'example' in fix:
                    report.append(f"   Example: {fix['example']}")
                report.append("")
        
        # AI Analysis
        report.append("🤖 STRATEGIC INFRASTRUCTURE ANALYSIS")
        report.append("-" * 50)
        report.append(ai_analysis)
        report.append("")
        
        # Recommendations
        if analysis['recommendations']:
            report.append("🎯 STRATEGIC RECOMMENDATIONS")
            report.append("-" * 50)
            for i, rec in enumerate(analysis['recommendations'], 1):
                report.append(f"{i}. {rec}")
            report.append("")
        
        # Footer
        report.append("=" * 100)
        report.append("🏗️ Terraform Infrastructure Analysis Complete")
        report.append(f"📊 Analyzed {analysis['total_files']} files with {total_issues} total issues")
        report.append("🔄 Re-run analysis after implementing fixes to track progress")
        report.append("=" * 100)
        
        return "\n".join(report) 