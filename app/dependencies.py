from app.infra.execution_client import ExecutionClient


def get_execution_client() -> ExecutionClient:
    """
    Get singleton ExecutionClient instance.
    
    ExecutionClient uses __new__ method to ensure singleton behavior,
    so direct constructor call always returns the same instance.
    """
    return ExecutionClient()


def get_current_user():
    pass


def get_admin_user():
    pass
