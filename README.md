# Literature Screening Tool

用于元分析和文献计量的自动化系统筛选工具 / Automated Literature Screening Tool for Meta-Analysis

[![Version](https://img.shields.io/badge/version-1.2.3-blue.svg)](https://github.com/Jake-yutong/Literature-Screening-Tool)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Start application
python app.py

# Or use launch script
python scripts/launch.py
```

Access the application at http://127.0.0.1:5000

### DeepSeek V4

Choose **DeepSeek V4 Pro** for the strongest screening quality or **DeepSeek V4 Flash** for faster, lower-cost batches. Both choices use `https://api.deepseek.com`, enable thinking mode with `reasoning_effort="high"`, and accept the same DeepSeek API key.

Before screening, enter the API key and click **Test API Connection**. The test sends one non-thinking request capped at 8 output tokens and reports the selected model and latency. If an AI request fails during formal screening, the task now stops with a categorized error instead of silently treating unscreened papers as retained.

## Core Features

- **Multi-format Support**: CSV, Excel (.xlsx/.xls), RIS, BibTeX, RTF, TXT
- Files downloaded as `cleaned_data_*.csv` can be uploaded again for a subsequent screening run.
- **Keyword-based Filtering**: Title/Abstract/Journal blacklists
- **AI-powered Screening**: Select DeepSeek V4 Pro, DeepSeek V4 Flash, or MiniMax-M2.1
- **Intelligent Deduplication**: DOI and title-based duplicate detection
- **Bilingual Interface**: Instant switching between English and Chinese
- **Professional UI**: Dark/Light theme with academic styling

## Project Structure

```
Literature-Screening-Tool/
├── app.py                  # Flask main application
├── requirements.txt        # Python dependencies
├── Procfile               # Deployment configuration
├── literature_screener.py # Core screening logic
├── templates/             # HTML templates
│   └── index.html
├── static/                # Static resources
├── docs/                  # Documentation
│   ├── README.md          # Detailed documentation
│   ├── USER_GUIDE.md      # User guide
│   ├── CHANGELOG.md       # Version history
│   ├── AI_MODEL_GUIDE.md  # AI model guide
│   └── ...
├── scripts/               # Scripts
│   ├── launch.py          # Launch script
│   ├── start.sh           # Linux startup
│   └── start.bat          # Windows startup
├── tests/                 # Tests
│   └── verify_app.py
└── data/                  # Test data
    ├── test_data.csv
    ├── test_data.ris
    └── test_data.bib
```

## Documentation

- [Complete Documentation](docs/README.md) - Full usage guide
- [User Guide](docs/USER_GUIDE.md) - Detailed operation steps
- [Changelog](docs/CHANGELOG.md) - Version history
- [AI Model Guide](docs/AI_MODEL_GUIDE.md) - AI screening documentation

## Development

```bash
# Install development dependencies
pip install -r requirements.txt

# Run tests
python tests/verify_app.py

# Start development server
python app.py
```

## Version

Current Version: **v1.2.3** (2025-12-23)

See [Changelog](docs/CHANGELOG.md) for detailed update information.

## Contributing

Issues and Pull Requests are welcome.

## License

MIT License - See LICENSE file for details.

## Author

LI Yutong (Jake) - [GitHub](https://github.com/Jake-yutong)

## Citation

If this tool is helpful for your research, please consider citing it in your publications.

