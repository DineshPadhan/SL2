from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "message": "Validation failed",
                "errors": exc.errors(),
                "path": str(request.url.path),
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, (dict, list)) else {"message": exc.detail}
        return JSONResponse(status_code=exc.status_code, content={"error": detail, "path": str(request.url.path)})

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
        error_text = str(getattr(exc, 'orig', exc))
        lowered = error_text.lower()
        status_code = status.HTTP_404_NOT_FOUND if 'foreign key' in lowered else status.HTTP_422_UNPROCESSABLE_ENTITY
        message = 'Related resource not found' if status_code == status.HTTP_404_NOT_FOUND else 'Database constraint violated'
        return JSONResponse(
            status_code=status_code,
            content={
                "error": {"message": message, "detail": error_text},
                "path": str(request.url.path),
            },
        )
