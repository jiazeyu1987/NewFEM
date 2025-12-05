# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.
不要创建临时文件，测试文件，直接需改文件
## Project Overview

NewFEM (New Focused Emboli Monitor) is a real-time HEM (High-Echoic Events) detection system that simulates a 60 FPS data generation system with peak detection capabilities. The system uses a modern three-tier architecture with FastAPI backend, vanilla JavaScript web frontend, and Python GUI client, all communicating via RESTful APIs for maximum compatibility.

## Project Structure

```
NewFEM/
├── CLAUDE.md                    # This file - guidance for Claude Code
├── fem_config.json             # Central configuration file for all components
├── backends/                    # FastAPI backend application
│   ├── run.py                  # Main entry point
│   ├── requirements.txt        # Python dependencies
│   └── app/
│       ├── api/
│       │   └── routes.py      # FastAPI routes and endpoints
│       ├── core/
│       │   ├── processor.py   # Background data processing (60 FPS)
│       │   ├── data_store.py  # Thread-safe circular buffer
│       │   ├── roi_capture.py # ROI capture functionality
│       │   └── enhanced_peak_detector.py
│       ├── utils/
│       │   └── roi_image_generator.py
│       ├── config.py          # Pydantic settings
│       ├── models.py          # Pydantic models
│       └── logging_config.py  # Logging configuration
├── python_client/              # Python GUI client application
│   ├── run_realtime_client.py # Main entry point for Python GUI (recommended)
│   ├── http_realtime_client.py # Full-featured HTTP client with tkinter GUI (62KB)
│   ├── simple_http_client.py  # Simplified HTTP client (16KB)
│   ├── realtime_plotter.py    # matplotlib-based real-time plotting component
│   ├── local_config_loader.py # Configuration management from fem_config.json
│   ├── enhanced_ui.py          # Enhanced GUI implementation
│   ├── client.py              # Core HTTP client functionality
│   ├── socket_client.py       # Legacy socket client for TCP protocol
│   └── test_config_integration.py # Configuration integration tests
├── fronted/                    # Web frontend application (note: typo in name)
│   └── index.html             # Complete vanilla JS application
└── doc/                       # Comprehensive documentation
    ├── system-architecture.md # System architecture (Chinese)
    ├── api-interface-spec.md  # Detailed API specification
    ├── backend-requirements.md # Backend requirements (Chinese)
    ├── frontend-requirements.md # Frontend requirements (Chinese)
    ├── data-specifications.md # Data format specifications
    ├── python_client/README.md # Python client development guide
    └── Various Chinese feature documentation files
```

## Common Commands

### Running the Application

#### Full System (Backend + Web Frontend)
```bash
# Start the backend server
cd backends && python run.py

# Then open the web frontend in a browser:
# Load fronted/index.html in a web browser
# Or use a simple HTTP server for the frontend:
cd fronted && python -m http.server 3000
```

#### Python GUI Client
```bash
# Start the backend server first
cd backends && python run.py

# Then start the Python GUI client in a separate terminal
cd python_client && python run_realtime_client.py
```

### Development Setup
```bash
# Install backend dependencies
cd backends && pip install -r requirements.txt

# Install Python client dependencies
pip install requests matplotlib pillow numpy

# Development server with auto-reload (backend only)
cd backends && uvicorn app.api.routes:app --reload --host 0.0.0.0 --port 8421

# Frontend development (no build tools required)
# Simply open fronted/index.html in browser or use HTTP server
```

### Code Quality
**Note: No automated code quality tools are currently configured.** The project doesn't include black, mypy, flake8, or other linting tools. To add code quality tools:
```bash
# Install formatting and linting tools (if needed)
cd backends && pip install black mypy flake8

# Code formatting (once configured)
cd backends && black .

# Type checking (once configured)
cd backends && mypy .

# Linting (once configured)
cd backends && flake8 .
```

### Testing
**Note: No testing framework is currently configured.** The codebase has manual test files (`test_*.py`) but no automated testing setup. To add testing:
```bash
# Install pytest (if needed)
cd backends && pip install pytest

# Run tests (once configured)
cd backends && python -m pytest
```

## Architecture Overview

### High-Level Architecture
```
Frontend (Vanilla JS + Canvas) ←→ HTTP/JSON API ←→ FastAPI Backend
     ↓                                      ↓
Real-time Chart Rendering              Data Processing Pipeline
     ↓                                      ↓
VS Code-style UI                    60 FPS Signal Simulation
                                        ↓
                                  Peak Detection Algorithm
                                        ↓
                                  Thread-safe Data Storage
```

### Backend Architecture (FastAPI)

**Core Components:**
- `backends/app/api/routes.py`: FastAPI application with all REST endpoints (HTTP API on port 8421)
- `backends/app/core/socket_server.py`: Traditional TCP socket server (legacy protocol on port 30415)
- `backends/app/core/processor.py`: Background thread generating simulated data at 60 FPS
- `backends/app/core/data_store.py`: Thread-safe circular buffer for time-series data
- `backends/app/core/roi_capture.py`: ROI capture and image processing functionality
- `backends/app/core/enhanced_peak_detector.py`: Enhanced peak detection algorithms
- `backends/app/core/config_manager.py`: Centralized configuration management from JSON
- `backends/app/models.py`: Pydantic models for API request/response validation
- `backends/app/config.py`: Environment-based configuration using Pydantic BaseSettings
- `backends/app/utils/roi_image_generator.py`: Generates ROI visualizations as base64 images
- `backends/app/logging_config.py`: Structured logging configuration

**Entry Point:**
- `backends/run.py`: Main application entry point that initializes logging and starts FastAPI server

**Data Flow:**
1. `DataProcessor` background thread generates sinusoidal signals with noise (started manually via UI)
2. Peak detection algorithm identifies signals exceeding threshold (baseline + 5.0)
3. `DataStore` maintains circular buffer (default 100 points) with thread safety
4. API endpoints provide real-time access via HTTP polling

**Key Design Patterns:**
- Producer-Consumer: DataProcessor produces, API endpoints consume
- Singleton: Global `processor` and `data_store` instances
- Thread-Safe: All data access uses `threading.Lock()`
- Configuration as Code: Environment variables with `NEWFEM_` prefix

### Frontend Architecture (Vanilla JavaScript)

**Core Components in `fronted/index.html`:**
- **Connection Manager**: Handles server connectivity and health checks
- **API Client**: Fetches real-time data and sends control commands
- **WaveformChart**: Canvas-based real-time chart rendering (20 FPS)
- **RoiRenderer**: Renders ROI data as base64 images
- **Control System**: Handles start/stop/pause detection commands

**Real-time Data Polling:**
- System status: Every 5 seconds
- Real-time data: Every 50ms (20 FPS display, backend generates at 45 FPS)
- Auto-reconnection with exponential backoff
- Chart rendering: Canvas-based at 20 FPS for performance

**UI Architecture:**
- VS Code-styled dark theme interface
- Collapsible side panels (System Status, Display Controls, ROI, Detection Control)
- Real-time chart with zoom (0.5x-3.0x) and tooltip support
- Mock mode for offline development

## Configuration

### Environment Variables (Backend)
Primary configuration is handled through `fem_config.json`. Environment variables provide overrides:
```bash
NEWFEM_HOST=0.0.0.0              # Server host (from fem_config.json)
NEWFEM_API_PORT=8421             # HTTP API port (from fem_config.json)
NEWFEM_SOCKET_PORT=30415         # Legacy socket port (from fem_config.json)
NEWFEM_LOG_LEVEL=INFO            # Logging level (INFO, DEBUG, WARNING, ERROR)
NEWFEM_BUFFER_SIZE=100           # Circular buffer size (from fem_config.json)
NEWFEM_FRAME_RATE=45             # Data generation FPS (from fem_config.json, not 60)
NEWFEM_PASSWORD=31415            # Control command password (from fem_config.json)
NEWFEM_ENABLE_CORS=True          # CORS configuration (from fem_config.json)
```

**Note**: The actual default frame rate is 45 FPS (not 60) as configured in `fem_config.json`.

### Frontend Configuration
- Server URL: Configurable via UI (default: `http://localhost:8421`)
- Mock mode: Toggle for offline development
- Chart zoom: 0.5x to 3.0x with slider control
- Data point limit: Default 100 points (configurable)

## API Endpoints

### System Management
- `GET /health`: Health check
- `GET /status`: System status and metrics

### Real-time Data
- `GET /data/realtime?count=100`: Time-series data with ROI visualization
- Returns: JSON with time series, ROI image data, peak signals, baseline

### Control Commands
- `POST /control`: Execute system commands (requires password)
  - Commands: `start_detection`, `stop_detection`, `pause_detection`, `resume_detection`
  - Authentication: Password via form field (default: `31415`)

### Analysis
- `POST /analyze`: Video analysis interface (supports both file upload and real-time mode)
- Returns: Analysis results with events, baseline calculations, and statistical data

### Legacy Socket Protocol (Port 30415)
- **For legacy clients**: TCP socket server provides backward compatibility
- **Format**: Raw JSON messages over TCP connection
- **Usage**: Primarily for older Python client implementations
- **Note**: Modern clients should use HTTP API for better compatibility

## Development Guidelines

### Backend Development
- All API responses use consistent Pydantic models from `models.py`
- Thread safety is critical - always use locks when accessing `data_store`
- Follow the existing logging patterns with structured log messages
- Environment variables should have sensible defaults
- Add new endpoints to the router in `routes.py`

### Frontend Development
- Follow the existing component structure and naming conventions
- Use the VS Code theme variables for consistent styling
- Canvas rendering should maintain 20 FPS performance
- All API calls should use the `apiClient` wrapper for consistent error handling
- Maintain mock mode compatibility for offline development

### Adding New Features
1. Backend: Add new models to `models.py`, implement logic in appropriate core module
2. API: Add new endpoint in `routes.py` with proper error handling and logging
3. Frontend: Add UI controls in side panels, integrate with existing polling system
4. Documentation: Update this file and the comprehensive docs in `doc/` directory

## Project Status

### Current State
- **Active Development**: Project is actively maintained with recent commits
- **Git Status**: Clean working directory (as of last analysis)
- **Modified Files**: `backends/app/fem_config.json` (currently modified)
- **Branch**: `main` (up to date with origin/main)

### Recent Development
- Enhanced UI implementation for Python client
- Improved configuration management
- Real-time plotting capabilities
- Mock mode support for frontend development

## Important Notes

- **Real-time Performance**: System is designed for 45 FPS data generation and 20 FPS display updates
- **Manual Data Processing**: Data processing must be started manually via the UI control panel (not automatic)
- **Authentication**: Control commands require password authentication (default: `31415`)
- **Data Persistence**: No database - uses in-memory circular buffer only
- **Mock Mode**: Frontend supports offline mock mode for development without backend
- **Thread Safety**: Critical due to concurrent data generation and API access
- **Error Handling**: Unified error response format across all API endpoints
- **Compatibility**: Uses standard HTTP/JSON instead of WebSocket for maximum compatibility
- **Directory Naming**: Note the typo in directory name "fronted" (should be "frontend")

## Troubleshooting

### Common Issues
- **Connection Refused**: Ensure backend is running on port 8421
- **No Data Display**: Check if data processing is started via control panel (click "开始分析")
- **Performance Issues**: Reduce polling frequency or buffer size
- **CORS Errors**: Verify CORS configuration in backend settings
- **Testing Not Available**: No test framework is currently configured

### Debug Mode
- Backend: Set `NEWFEM_LOG_LEVEL=DEBUG` for detailed logs
- Frontend: Use browser dev tools to monitor network requests and console output
- Mock mode: Enable for frontend testing without backend dependency