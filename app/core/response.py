from typing import Optional, Any, Dict


def create_success_response(data: Optional[Any] = None) -> Dict[str, Any]:
    """Create a standardized success response following CommonApiResponse format"""
    response = {"success": True}
    if data is not None:
        response["data"] = data
    return response


def create_error_response(code: str, message: str, details: Optional[Any] = None) -> Dict[str, Any]:
    """Create a standardized error response following CommonApiResponse format"""
    error = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    
    return {
        "success": False,
        "error": error
    }