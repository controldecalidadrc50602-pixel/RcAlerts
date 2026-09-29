import sys
import os
import traceback

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

try:
    from main import app
except Exception as e:
    tb = traceback.format_exc()
    print("CRITICAL STARTUP ERROR IN MAIN:", tb)
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    app = FastAPI(title="Error Fallback")
    
    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"])
    async def catch_all_error(path: str):
        return JSONResponse(status_code=500, content={"error": "Module startup error in Vercel", "traceback": tb})

