"""MediTrace public API: referral review plus closed legacy routes."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from referral_review.app import create_app as create_referral_app


load_dotenv()
app = FastAPI(title="MediTrace Referral Review API", docs_url=None, redoc_url=None)
app.mount("/api/v1", create_referral_app())


@app.api_route("/health", methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
@app.api_route("/api", methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
@app.api_route("/api/{legacy_path:path}", methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def retired_api(request: Request, legacy_path: str = ""):
    """Reject old API paths before body parsing, database access or service imports."""
    return JSONResponse(
        {"error": "LEGACY_API_RETIRED", "message": "This API has been retired. Use the referral review workspace.",
         "new_url": "/workspace"},
        status_code=410,
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


if __name__ == "__main__":
    import uvicorn
    from referral_review.operations.access_logging import access_log_config
    uvicorn.run(app, host="0.0.0.0", port=8000, log_config=access_log_config())
