import sys
import os
import traceback

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

try:
    from main import app as original_app
except Exception as e:
    tb = traceback.format_exc()
    print("CRITICAL STARTUP ERROR IN MAIN:", tb)
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    original_app = FastAPI(title="Error Fallback")
    
    @original_app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"])
    async def catch_all_error(path: str):
        return JSONResponse(status_code=500, content={"error": "Module startup error in Vercel", "traceback": tb})

# Wrapper ASGI a prueba de balas para capturar cualquier excepción no manejada
async def app(scope, receive, send):
    if scope["type"] == "lifespan":
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return
    try:
        await original_app(scope, receive, send)
    except Exception as exc:
        tb = traceback.format_exc()
        print("CRITICAL ASGI RUNTIME ERROR:", tb)
        from fastapi.responses import JSONResponse
        err_resp = JSONResponse(
            status_code=500,
            content={"error": "Unhandled ASGI Exception", "detail": str(exc), "traceback": tb}
        )
        await err_resp(scope, receive, send)


