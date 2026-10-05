from fastapi import APIRouter

router = APIRouter()


@router.get("/health", include_in_schema=True)
def health() -> dict[str, str]:
    """Report process health without querying external dependencies."""
    return {"status": "ok"}
