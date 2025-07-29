
# Kubernetes Validation Tool with AI-Powered Reporting

A comprehensive tool that uses **kubeval** to validate Kubernetes YAML files from repositories and generates curated reports using an AI agent.

## 🚀 Features

- **Repository Validation**: Clone and validate Kubernetes files from any Git repository
- **Local File Validation**: Validate local Kubernetes YAML files
- **AI-Powered Reports**: Generate detailed, curated reports with insights and recommendations
- **Error Categorization**: Automatically categorize and prioritize validation errors
- **Multiple Output Formats**: Support for both text and JSON report formats
- **Flexible Configuration**: Environment-based configuration for easy deployment

## 📋 Prerequisites

### Required Software

1. **kubeval**: Install from [kubeval releases](https://github.com/instrumenta/kubeval/releases)
   ```bash
   # macOS
   brew install kubeval
   
   # Linux
   wget https://github.com/instrumenta/kubeval/releases/latest/download/kubeval-linux-amd64.tar.gz
   tar xf kubeval-linux-amd64.tar.gz
   sudo cp kubeval /usr/local/bin
   ```

2. **Git**: Required for repository cloning
3. **Python 3.8+**: Required for running the tool

### Python Dependencies

Install the required Python packages:

```bash
pip install -r requirements.txt
```

## ⚙️ Configuration

Create a `.env` file in the project root with the following variables:

```env
# AI Agent Configuration (Required)
API_KEY=your_api_key_here
API_URL=your_api_url_here
MODEL_NAME=your_model_name_here

# Repository Configuration (Required)
REPO_URL=https://github.com/your-org/your-repo

# Optional Configuration
KUBEVAL_SCHEMA_LOCATION=https://raw.githubusercontent.com/yannh/kubernetes-json-schema/master/
OUTPUT_FORMAT=text
REPORT_SEVERITY_LEVEL=error
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `API_KEY` | ✅ | API key for your AI service |
| `API_URL` | ✅ | Base URL for your AI service API |
| `MODEL_NAME` | ✅ | Name of the AI model to use |
| `REPO_URL` | ✅ | Default Git repository URL to validate |
| `KUBEVAL_SCHEMA_LOCATION` | ❌ | Custom kubeval schema location |
| `OUTPUT_FORMAT` | ❌ | Output format: `text` or `json` |
| `REPORT_SEVERITY_LEVEL` | ❌ | Minimum severity level for reporting |

## 🔧 Usage

### Basic Repository Validation

Validate the repository specified in your `.env` file:

```bash
python validate.py
```

### Custom Repository Validation

Validate a specific repository:

```bash
python validate.py --repo https://github.com/kubernetes/examples
```

### Branch-Specific Validation

Validate a specific branch:

```bash
python validate.py --repo https://github.com/kubernetes/examples --branch main
```

### Local File Validation

Validate local Kubernetes files:

```bash
python validate.py --files deployment.yaml service.yaml configmap.yaml
```

### Save Report to File

Save the validation report to a file:

```bash
python validate.py --output validation-report.txt
```

### JSON Output Format

Generate a JSON report:

```bash
python validate.py --format json --output validation-report.json
```

## 📊 Report Structure

The tool generates comprehensive reports with the following sections:

### 📈 Validation Summary
- Total files checked
- Valid vs. invalid files
- Success rate percentage
- Total error count

### 🚨 Error Breakdown
- Categorized error types
- Error frequency analysis
- Priority ranking

### 💡 Immediate Recommendations
- Automated recommendations based on error patterns
- Actionable next steps
- Best practices suggestions

### 🤖 AI Analysis
- Executive summary
- Key issues identification
- Security implications
- Performance impact assessment
- Specific remediation steps
- Risk assessment

## 🏗️ Architecture

The tool consists of four main components:

### 1. KubevalTool (`kubeval_tool.py`)
- Wraps the kubeval binary
- Handles validation of individual files and directories
- Provides batch validation capabilities
- Supports custom schema locations

### 2. RepoFetcher (`repo_fetcher.py`)
- Clones Git repositories
- Identifies Kubernetes YAML files
- Manages temporary directories
- Supports branch-specific validation

### 3. ValidationAgent (`validation_agent.py`)
- Processes kubeval results
- Generates AI-powered insights
- Categorizes and prioritizes errors
- Creates structured reports

### 4. KubernetesValidator (`validate.py`)
- Main orchestrator class
- Handles command-line arguments
- Manages environment configuration
- Coordinates all components

## 🔍 Error Categories

The tool automatically categorizes validation errors into:

- **Schema Validation**: Basic schema compliance issues
- **API Version**: Outdated or invalid API versions
- **Resource Kind**: Invalid or missing resource kinds
- **Metadata**: Metadata-related issues
- **Specification**: Resource specification problems
- **Missing Required Fields**: Required fields not present
- **Format/Syntax**: YAML syntax and formatting issues
- **File Not Found**: Missing or inaccessible files
- **Other**: Uncategorized errors

## 🚦 Exit Codes

The tool uses different exit codes to indicate various states:

- `0`: Success (all files valid)
- `1`: General error (configuration, network, etc.)
- `2`: No Kubernetes files found
- `3`: Validation failures found

## 🔧 Development

### Running Tests

```bash
# Test kubeval installation
python -c "from kubeval_tool import KubevalTool; KubevalTool()"

# Test with sample files
python validate.py --files examples/*.yaml
```

### Extending the Tool

#### Adding New Error Categories

Modify the `_categorize_error` method in `ValidationAgent`:

```python
def _categorize_error(self, error_message: str) -> str:
    error_lower = error_message.lower()
    
    if 'your_pattern' in error_lower:
        return 'Your Category'
    # ... existing categories
```

#### Customizing AI Prompts

Modify the `_create_analysis_prompt` method in `ValidationAgent` to adjust the AI analysis prompt.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License.

## 🆘 Troubleshooting

### Common Issues

1. **kubeval not found**: Ensure kubeval is installed and in your PATH
2. **Repository access denied**: Check repository URL and authentication
3. **AI API errors**: Verify API key, URL, and model name in `.env`
4. **No Kubernetes files found**: Check repository contents and file patterns

### Debug Mode

For detailed error information, check the console output during validation runs.

## 📞 Support

For issues and feature requests, please create an issue in the project repository.
