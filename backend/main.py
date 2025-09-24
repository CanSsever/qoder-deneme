"""
Main entry point for OneShot Face Swapper API.
"""
import uvicorn
from apps.api.main import app

if __name__ == "__main__":
    uvicorn.run(
        "apps.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )