# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NewFEM (New Focused Emboli Monitor) is a real-time HEM (High-Echoic Events) detection system that simulates a 60 FPS data generation system with peak detection capabilities. The system uses a modern web architecture with FastAPI backend and vanilla JavaScript frontend, communicating via RESTful APIs instead of WebSocket for better compatibility.

## Common Commands

### Running the Application
```bash
# Start the full system (backend + frontend)
# From the root directory:
python backends/run.py

# Then open the frontend in a browser:
# Load fronted/index.html in a web browser
# Or use a simple HTTP server for the frontend:
cd fronted && python -m http.server 3000
```

### Development Setup
```bash
# Install Python dependencies
cd backends && pip install -r requirements.txt

# Development server with auto-reload (backend only)
cd backends && uvicorn app.api.routes:app --reload --host 0.0.0.0 --port 8421

# Frontend development (no build tools required)
# Simply open fronted/index.html in browser or use HTTP server
```

### Testing and Code Quality
```bash
# Backend testing
cd backends && python -m pytest  # (if pytest is configured)

# Code formatting
cd backends && black .

# Type checking
cd backends && mypy .
```

### Docker Deployment (if needed)
```bash
# Build and run with Docker
cd backends && docker build -t newfem .
docker run -p 8421:8421 newfem
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
- `backends/app/api/routes.py`: FastAPI application with all REST endpoints
- `backends/app/core/processor.py`: Background thread generating simulated data at 60 FPS
- `backends/app/core/data_store.py`: Thread-safe circular buffer for time-series data
- `backends/app/models.py`: Pydantic models for API request/response validation
- `backends/app/config.py`: Centralized configuration using Pydantic BaseSettings
- `backends/app/utils/roi_image_generator.py`: Generates ROI visualizations as base64 images
- `backends/app/logging_config.py`: Structured logging configuration

**Data Flow:**
1. `DataProcessor` background thread generates sinusoidal signals with noise
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
- Real-time data: Every 50ms (20 FPS)
- Auto-reconnection with exponential backoff

**UI Architecture:**
- VS Code-styled dark theme interface
- Collapsible side panels (System Status, Display Controls, ROI, Detection Control)
- Real-time chart with zoom (0.5x-3.0x) and tooltip support
- Mock mode for offline development

## Configuration

### Environment Variables (Backend)
```bash
NEWFEM_HOST=0.0.0.0              # Server host
NEWFEM_PORT=8421                 # API port
NEWFEM_LOG_LEVEL=INFO           # Logging level
NEWFEM_BUFFER_SIZE=100          # Circular buffer size
NEWFEM_FRAME_RATE=60            # Data generation FPS
NEWFEM_PASSWORD=31415           # Control command password
NEWFEM_ENABLE_CORS=True         # CORS configuration
```

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

## Important Notes

- **Real-time Performance**: System is designed for 60 FPS data generation and 20 FPS display updates
- **Authentication**: Control commands require password authentication (default: `31415`)
- **Data Persistence**: No database - uses in-memory circular buffer only
- **Mock Mode**: Frontend supports offline mock mode for development without backend
- **Thread Safety**: Critical due to concurrent data generation and API access
- **Error Handling**: Unified error response format across all API endpoints
- **Compatibility**: Uses standard HTTP/JSON instead of WebSocket for maximum compatibility

## Troubleshooting

### Common Issues
- **Connection Refused**: Ensure backend is running on port 8421
- **No Data Display**: Check if data processing is started via control panel
- **Performance Issues**: Reduce polling frequency or buffer size
- **CORS Errors**: Verify CORS configuration in backend settings

### Debug Mode
- Backend: Set `NEWFEM_LOG_LEVEL=DEBUG` for detailed logs
- Frontend: Use browser dev tools to monitor network requests and console output
- Mock mode: Enable for frontend testing without backend dependency