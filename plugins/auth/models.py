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
    
    gitlab_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=True)
    
    def __repr__(self):
        return f'<DemoUser {self.username}>'
    
    def to_dict(self):
        """Convert model to dictionary"""
        return {
            'gitlab_id': self.gitlab_id
        }