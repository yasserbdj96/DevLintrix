# plugins/auth/models.py
from core.database import db
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from flask_login import UserMixin

class DemoUser(db.Model):
    """Example user model for demo plugin"""
    __tablename__ = 'demo_users'
    __table_args__ = {'extend_existing': True}

    # Primary Key (will be merged with base User model)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    gitlab_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=True)
    
    def __repr__(self):
        return f'<User OAuth Extensions>'
    
    def to_dict_oauth(self):
        """Convert OAuth fields to dictionary"""
        return {
            'gitlab_id': self.gitlab_id
        }