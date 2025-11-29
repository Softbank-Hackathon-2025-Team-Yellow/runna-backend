from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db


def get_current_user():
    pass


def get_admin_user():
    pass