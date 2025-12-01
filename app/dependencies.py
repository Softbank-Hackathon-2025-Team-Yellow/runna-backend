from app.infra.execution_client import ExecutionClient


# Singleton instance of ExecutionClient
_execution_client_instance: ExecutionClient = None


def get_execution_client() -> ExecutionClient:
    """
    Get or create singleton ExecutionClient instance.
    
    This ensures that:
    1. Only one ExecutionClient exists (shared waiters map)
    2. Only one Redis connection pool is used
    3. The callback listener is shared across all requests
    """
    global _execution_client_instance
    if _execution_client_instance is None:
        _execution_client_instance = ExecutionClient()
    return _execution_client_instance


def get_current_user():
    pass


def get_admin_user():
    pass
