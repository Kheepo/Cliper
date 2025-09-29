#!/usr/bin/env python3
"""
Minimal FastAPI app to test form data handling
"""

from fastapi import FastAPI, Form
from typing import List
import uvicorn

app = FastAPI()

@app.post("/test-form")
async def test_form_endpoint(
    segment_ids: List[str] = Form(...),
    platforms: List[str] = Form(...)
):
    """Test endpoint for form data"""
    return {
        "segment_ids": segment_ids,
        "platforms": platforms,
        "message": "Form data received successfully"
    }

if __name__ == "__main__":
    print("Starting minimal test server on port 8002...")
    uvicorn.run(app, host="0.0.0.0", port=8002)