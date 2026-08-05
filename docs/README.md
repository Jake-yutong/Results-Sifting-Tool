# Literature Screening Tool v1.2.3

A Python-based tool for preliminary screening in systematic reviews, meta-analyses, and bibliometric studies. This tool facilitates the filtering of large literature datasets exported from Web of Science and Scopus.

## What's New in v1.2.3

- **Performance Optimization**: Removed double verification step for 50% faster AI screening
- **Enhanced Stability**: Improved error handling and retry mechanisms for MiniMax-M2
- **Model Streamlining**: Focused on two reliable AI providers (DeepSeek and MiniMax-M2)
- **Rate Limit Management**: Smart retry with exponential backoff for API calls

### Key Features from v1.2.0

- **Multi-Model AI Support**: Choose DeepSeek V4 Pro, DeepSeek V4 Flash, or MiniMax-M2.1
- **MiniMax-M2 Integration**: Advanced AI screening with thinking process visualization
- **Flexible Model Selection**: Switch between different AI providers based on your needs
- **Unified API Interface**: Simplified API key management for multiple providers

### Previous Updates (v1.1.0)

- **Bilingual Interface**: Seamless EN/Chinese language switching
- **RIS File Support**: Import and export RIS (Research Information Systems) format
- **Multiple Export Formats**: CSV, Excel (.xlsx/.xls), TXT, and RIS
- **Professional UI**: Refined academic-style interface with improved dark mode
- **Enhanced Performance**: Optimized file processing and format conversion

## Features

- **Batch processing**: Supports multiple file uploads (.xlsx, .xls, .csv, .ris, .txt)
- **Format standardization**: Automatically converts Web of Science export format to Scopus-compatible format for VOSviewer
- **Keyword-based exclusion**: Filter records by title, abstract, or journal name
- **Multi-Model AI Screening** (optional): 
  - **DeepSeek V4**: Pro for quality or Flash for faster, lower-cost screening
  - **MiniMax-M2**: Advanced reasoning with thinking process visualization
  - Natural language-based filtering criteria for both models
- **Flexible export options**: Download results in CSV, Excel, TXT, or RIS format
- **Structured output**:
  - Retained records for downstream analysis
  - Excluded records with documented exclusion reasons (for PRISMA reporting)

## Installation

### System Requirements
- **Python 3.8 or higher** (Must be properly installed, not Windows Store version)
- pip package manager
- Supported operating systems: Windows 10/11, macOS 10.14+, Linux (Ubuntu 18.04+)

### Option 1: One-Click Launch (Recommended)

**Windows:**

If you don't have Python installed:
1. Download Python from https://www.python.org/downloads/
2. IMPORTANT: During installation, check "Add Python to PATH"
3. Complete the installation and restart your computer

To run the tool:
1. Download this repository: Click the green "Code" button, then "Download ZIP"
2. Extract the ZIP file to any folder (e.g., Desktop or Documents)
3. Double-click `start.bat`
   - First run: Dependencies will be installed automatically (takes 1-2 minutes)
   - The terminal window will stay open showing server status
   - After approximately 3 seconds, your browser will open automatically to `http://127.0.0.1:5000`
4. To stop: Press `Ctrl+C` in the terminal window

**macOS:**

Method 1: Right-click shortcut (Recommended)
1. Download and extract this repository to any folder (e.g., Downloads or Desktop)
2. In Finder, locate the extracted folder
3. Right-click on the folder's empty space, select "New Terminal at Folder"
4. In the terminal window that appears, enter the following command (first run requires authorization):
   ```bash
   chmod +x start.sh && ./start.sh
   ```
5. Wait 3 seconds, the browser will automatically open `http://127.0.0.1:5000`
6. To stop the service: Press `Ctrl+C` in the terminal

Method 2: Manual navigation (if right-click menu does not have terminal option)
1. Open the "Terminal" application (in Applications > Utilities)
2. Type `cd ` (cd followed by a space)
3. Drag and drop the extracted folder from Finder directly into the terminal window
4. Press Enter, then run:
   ```bash
   chmod +x start.sh && ./start.sh
   ```

Common Issues:
- If prompted "Cannot be opened because it is from an unidentified developer": Right-click `start.sh`, select "Open", then click "Open" again to confirm
- If Python command does not exist: First install [Homebrew](https://brew.sh/), then run `brew install python3`

**Linux:**
1. Download and extract this repository
2. Open Terminal and navigate to the extracted folder:
   ```bash
   cd ~/Downloads/Literature-Screening-Tool  # 根据实际路径调整
   ```
3. Run the launcher script:
   ```bash
   chmod +x start.sh && ./start.sh
   ```
4. Your browser will open automatically to `http://127.0.0.1:5000`

### Option 2: Manual Installation

```bash
# Step 1: Clone the repository
git clone https://github.com/Jake-yutong/Results-Sifting-Tool.git

# Step 2: Navigate to the project directory
cd Results-Sifting-Tool

# Step 3: (Optional) Create a virtual environment
python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate

# Step 4: Install required packages
pip install -r requirements.txt

# Step 5: Launch the application
python app.py
```

The web interface will be available at `http://127.0.0.1:5000`.

### Troubleshooting

| Issue | Solution |
|-------|----------|
| Terminal closes immediately without output | Python is not installed correctly. Download from python.org and check "Add to PATH" during installation |
| "Python was not found" error | This is the Windows Store placeholder. Install real Python from python.org OR disable the placeholder in Settings → Apps → App execution aliases |
| Browser shows "Connection Refused" | Wait 5 seconds for the server to fully start, then refresh the page |
| Dependencies fail to install | Check your internet connection. If behind a proxy, configure pip with: `pip config set global.proxy http://your-proxy:port` |
| "Port 5000 already in use" (macOS) | **Automatic**: The tool will auto-switch to port 5001+<br>**Manual fix**: Disable AirPlay Receiver in System Settings → General → AirPlay Receiver (uncheck "Allow Handoff between this Mac and your iCloud devices") |
| "Address already in use" error | The tool automatically finds an available port. Check the terminal output for the actual port number |
| Excel file read errors | Ensure files are in `.xlsx`, `.xls`, or `.csv` format with UTF-8 encoding |

## AI Configuration (Optional)

This tool supports DeepSeek V4 Pro, DeepSeek V4 Flash, and MiniMax-M2.1 for intelligent literature screening. All choices use natural language criteria for flexible filtering.

### DeepSeek V4 Pro / V4 Flash

**Advantages:**
- V4 Pro prioritizes screening quality and complex decisions
- V4 Flash prioritizes response speed and lower cost
- High-effort thinking mode for both models
- Stable JSON output format

**Setup:**
1. Get your API key from [DeepSeek Platform](https://platform.deepseek.com/)
2. In the web interface, select "DeepSeek V4 Pro" or "DeepSeek V4 Flash"
3. Enter your API key in the "API Key" field
4. Add natural language exclusion criteria (e.g., "Exclude all papers not about K-12 education")

**API Endpoint:** `https://api.deepseek.com`

### MiniMax-M2.1

**Advantages:**
- Advanced reasoning with thinking process
- Higher accuracy for complex criteria
- Automatic retry mechanism with exponential backoff
- Handles ambiguous cases better

**Setup:**
1. Get your API key from [MiniMax Platform](https://platform.minimaxi.com/)
2. In the web interface, select "MiniMax-M2.1" from the model dropdown
3. Enter your API key in the "API Key" field
4. Add natural language exclusion criteria

**API Endpoints:**
- China: `https://api.minimaxi.com/anthropic`
- International: `https://api.minimax.io/anthropic`

### Performance Comparison

| Feature | DeepSeek V4 Pro | DeepSeek V4 Flash | MiniMax-M2.1 |
|---------|-----------------|-------------------|---------------|
| Speed | Moderate | Fastest | Moderate |
| Cost | Higher | Lower | Moderate |
| Thinking | High effort | High effort | Advanced |
| Best For | Complex screening | Large batches | Complex screening |

**Note:** The tool automatically selects the appropriate API endpoint based on your model choice.

## Usage

1. **Upload** literature export files (Web of Science or Scopus format)
2. **Configure** exclusion keywords for title/abstract and journal name fields
3. **(Optional)** Select AI model and provide API key for intelligent screening
4. **Run** the screening process
5. **Download** results:
   - `cleaned_data.csv` for bibliometric analysis (e.g., VOSviewer)
   - `removed_data.csv` for PRISMA flow diagram documentation

## Dependencies

| Package | Purpose |
|---------|---------|
| Flask | Web framework |
| Pandas | Data manipulation |
| OpenPyXL | Excel file handling |
| xlrd | Legacy Excel format support |
| openai | DeepSeek API integration (optional) |
| anthropic | MiniMax-M2 API integration (optional) |
| gunicorn | Production server |

## File Structure

```
├── app.py                  # Flask application
├── literature_screener.py  # Command-line interface
├── templates/
│   └── index.html          # Web interface
├── requirements.txt
├── start.bat               # Windows launcher
└── start.sh                # Unix launcher
```

## Citation

If you use this tool in your research, please cite:

```
Literature Screening Tool. Available at: https://github.com/Jake-yutong/Results-Sifting-Tool
```

## License

This project is provided for academic and research purposes.

