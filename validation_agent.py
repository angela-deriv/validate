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
    error_types: Dict[str, int]
    recommendations: List[str]


class ValidationAgent:
    """
    An AI agent that processes kubeval results and generates curated reports.
    """
    
    def __init__(self, api_key: str, api_url: str, model_name: str):
        self.api_key = api_key
        self.api_url = api_url
        self.model_name = model_name
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url=api_url
        )
    
    def analyze_validation_results(self, validation_results: List[Dict[str, Any]]) -> ValidationSummary:
        """
        Analyze kubeval validation results and create a summary.
        
        Args:
            validation_results: List of validation results from kubeval
            
        Returns:
            ValidationSummary object with analysis
        """
        total_files = len(validation_results)
        valid_files = sum(1 for result in validation_results if result.get('valid', False))
        invalid_files = total_files - valid_files
        
        # Count error types
        error_types = {}
        total_errors = 0
        
        for result in validation_results:
            if not result.get('valid', True):
                errors = result.get('errors', [])
                total_errors += len(errors)
                
                for error in errors:
                    error_category = self._categorize_error(error)
                    error_types[error_category] = error_types.get(error_category, 0) + 1
        
        # Generate recommendations based on error patterns
        recommendations = self._generate_recommendations(error_types, validation_results)
        
        return ValidationSummary(
            total_files=total_files,
            valid_files=valid_files,
            invalid_files=invalid_files,
            total_errors=total_errors,
            error_types=error_types,
            recommendations=recommendations
        )
    
    def generate_detailed_report(self, validation_results: List[Dict[str, Any]], 
                               repo_url: Optional[str] = None) -> str:
        """
        Generate a detailed report using AI analysis.
        
        Args:
            validation_results: List of validation results from kubeval
            repo_url: Optional repository URL for context
            
        Returns:
            Detailed report as a string
        """
        summary = self.analyze_validation_results(validation_results)
        
        # Prepare data for AI analysis
        context = {
            "summary": {
                "total_files": summary.total_files,
                "valid_files": summary.valid_files,
                "invalid_files": summary.invalid_files,
                "total_errors": summary.total_errors,
                "error_types": summary.error_types
            },
            "repo_url": repo_url,
            "timestamp": datetime.now().isoformat(),
            "detailed_results": validation_results[:10]  # Limit to first 10 for AI context
        }
        
        # Create AI prompt
        prompt = self._create_analysis_prompt(context)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a Kubernetes expert analyzing validation results. Provide detailed insights, prioritized recommendations, and actionable advice."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=2000,
                temperature=0.1
            )
            
            ai_analysis = response.choices[0].message.content
            
        except Exception as e:
            ai_analysis = f"AI analysis unavailable: {str(e)}"
        
        # Combine summary and AI analysis into final report
        report = self._format_final_report(summary, ai_analysis, repo_url)
        
        return report
    
    def _categorize_error(self, error_message: str) -> str:
        """Categorize error messages into types."""
        error_lower = error_message.lower()
        
        if 'schema' in error_lower or 'validation' in error_lower:
            return 'Schema Validation'
        elif 'apiversion' in error_lower:
            return 'API Version'
        elif 'kind' in error_lower:
            return 'Resource Kind'
        elif 'metadata' in error_lower:
            return 'Metadata'
        elif 'spec' in error_lower:
            return 'Specification'
        elif 'required' in error_lower or 'missing' in error_lower:
            return 'Missing Required Fields'
        elif 'format' in error_lower or 'syntax' in error_lower:
            return 'Format/Syntax'
        elif 'timeout' in error_lower:
            return 'Timeout'
        elif 'not found' in error_lower:
            return 'File Not Found'
        else:
            return 'Other'
    
    def _generate_recommendations(self, error_types: Dict[str, int], 
                                validation_results: List[Dict[str, Any]]) -> List[str]:
        """Generate recommendations based on error patterns."""
        recommendations = []
        
        # Priority recommendations based on error types
        if error_types.get('API Version', 0) > 0:
            recommendations.append(
                "🔄 Update API versions to current Kubernetes standards"
            )
        
        if error_types.get('Missing Required Fields', 0) > 0:
            recommendations.append(
                "📝 Add missing required fields in resource definitions"
            )
        
        if error_types.get('Schema Validation', 0) > 0:
            recommendations.append(
                "✅ Review and fix schema validation errors"
            )
        
        if error_types.get('Format/Syntax', 0) > 0:
            recommendations.append(
                "🔧 Fix YAML format and syntax issues"
            )
        
        # General recommendations
        total_errors = sum(error_types.values())
        if total_errors > 10:
            recommendations.append(
                "🎯 Consider implementing pre-commit hooks for validation"
            )
        
        return recommendations
    
    def _create_analysis_prompt(self, context: Dict[str, Any]) -> str:
        """Create a prompt for AI analysis."""
        return f"""
Please analyze these Kubernetes validation results and provide a comprehensive report:

VALIDATION SUMMARY:
- Total files checked: {context['summary']['total_files']}
- Valid files: {context['summary']['valid_files']}
- Invalid files: {context['summary']['invalid_files']}
- Total errors: {context['summary']['total_errors']}

ERROR BREAKDOWN:
{json.dumps(context['summary']['error_types'], indent=2)}

SAMPLE VALIDATION RESULTS:
{json.dumps(context['detailed_results'], indent=2)}

Please provide:
1. Executive Summary (2-3 sentences)
2. Key Issues Identified (prioritized list)
3. Security Implications (if any)
4. Performance Impact Assessment
5. Specific Remediation Steps
6. Best Practices Recommendations
7. Risk Assessment (High/Medium/Low)

Format your response in clear sections with actionable insights.
"""
    
    def _format_final_report(self, summary: ValidationSummary, 
                           ai_analysis: str, repo_url: Optional[str] = None) -> str:
        """Format the final report."""
        report = []
        
        # Header
        report.append("=" * 60)
        report.append("KUBERNETES VALIDATION REPORT")
        report.append("=" * 60)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        if repo_url:
            report.append(f"Repository: {repo_url}")
        report.append("")
        
        # Quick Stats
        report.append("📊 VALIDATION SUMMARY")
        report.append("-" * 30)
        report.append(f"Total Files:     {summary.total_files}")
        report.append(f"Valid Files:     {summary.valid_files}")
        report.append(f"Invalid Files:   {summary.invalid_files}")
        report.append(f"Total Errors:    {summary.total_errors}")
        
        # Success rate
        success_rate = (summary.valid_files / summary.total_files * 100) if summary.total_files > 0 else 0
        report.append(f"Success Rate:    {success_rate:.1f}%")
        report.append("")
        
        # Error Types
        if summary.error_types:
            report.append("🚨 ERROR BREAKDOWN")
            report.append("-" * 30)
            for error_type, count in sorted(summary.error_types.items(), 
                                          key=lambda x: x[1], reverse=True):
                report.append(f"{error_type}: {count}")
            report.append("")
        
        # Recommendations
        if summary.recommendations:
            report.append("💡 IMMEDIATE RECOMMENDATIONS")
            report.append("-" * 30)
            for rec in summary.recommendations:
                report.append(f"• {rec}")
            report.append("")
        
        # AI Analysis
        report.append("🤖 DETAILED ANALYSIS")
        report.append("-" * 30)
        report.append(ai_analysis)
        report.append("")
        
        # Footer
        report.append("=" * 60)
        report.append("End of Report")
        report.append("=" * 60)
        
        return "\n".join(report) 