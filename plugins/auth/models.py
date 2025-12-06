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
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=True)
    github_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    
    
    def __repr__(self):
        return f'<User OAuth Extensions>'
    
    def to_dict_oauth(self):
        """Convert OAuth fields to dictionary"""
        return {
            'username': self.username,
            'email': self.email,
            'github_id': self.github_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'is_active': self.is_active
        }