# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NewFEM is a Python-based FastAPI backend service for real-time signal processing and data analysis. It simulates a 60 FPS data generation system with peak detection capabilities, designed for finite element method (FEM) data processing.

## Common Commands

### Running the Application
```bash
# Start the FastAPI server with data processing system
python run.py

# Alternative: start directly with main module
python -m backends.main
```

### Development Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Development server (auto-reload)
uvicorn backends.app.api.routes:app --reload --host 0.0.0.0 --port 8421
```

### Testing
```bash
# No specific test framework is configured in this project
# Use pytest or unittest as needed for testing
```

### Code Quality
```bash
# Format code
black .

# Lint code
flake8 .

# Type checking
mypy .
```

## Architecture

### Core Components

**Data Flow Architecture:**
- `DataProcessor` (app/core/processor.py): Background thread running at 60 FPS to generate simulated signal data
- `DataStore` (app/core/data_store.py): Thread-safe circular buffer for time-series data storage
- FastAPI Routes (app/api/routes.py): REST API endpoints for real-time data access

**Key Design Patterns:**
- **Producer-Consumer Pattern**: DataProcessor produces data, API endpoints consume it
- **Singleton Pattern**: Global `processor` and `data_store` instances
- **Thread-Safe Operations**: All data access uses threading locks
- **Configuration Management**: Centralized settings with environment variable overrides

**Data Processing Pipeline:**
1. DataProcessor generates sinusoidal signals with noise at 60 FPS
2. Peak detection identifies signals exceeding threshold baseline
3. DataStore maintains circular buffer of configurable size
4. API endpoints provide real-time access to current state and historical data

### Configuration

All configuration is managed through `app/config.py` using Pydantic BaseSettings:
- Environment variables prefixed with `NEWFEM_`
- Default host: 0.0.0.0, API port: 8421
- Adjustable FPS, buffer size, and signal processing parameters
- CORS enabled by default

### API Endpoints

The service exposes REST endpoints for:
- `/health`: System health check
- `/status`: Current system status and real-time metrics
- `/data/latest`: Most recent frame data
- `/data/timeseries`: Historical time-series data
- `/analyze`: Signal analysis with ROI data processing

### Logging

- Structured logging with both file and console output
- Log files created in `logs/` directory with timestamps
- Debug-level logging for data processing, Info-level for API requests

## Important Notes

- The system simulates signal data for testing/development purposes
- Peak detection algorithm uses simple threshold-based approach
- All timestamps are UTC-based
- Thread safety is critical due to concurrent data generation and API access
- Configuration supports runtime environment variable overrides