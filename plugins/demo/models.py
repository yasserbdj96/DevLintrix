# plugins/demo/models.py
from core.database import db
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

class DemoUser(db.Model):
    """Example user model for demo plugin"""
    __tablename__ = 'demo_users'
    __table_args__ = {'extend_existing': True}
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gitlab_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=True)
    
    def __repr__(self):
        return f'<DemoUser {self.username}>'
    
    def to_dict(self):
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'gitlab_id': self.gitlab_id
        }

class DemoPost(db.Model):
    """Example post model for demo plugin"""
    __tablename__ = 'demo_posts'
    __table_args__ = {'extend_existing': True}
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey('demo_users.id'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    
    def __repr__(self):
        return f'<DemoPost {self.title}>'
    
    def to_dict(self):
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'author_id': self.author_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'published': self.published
        }