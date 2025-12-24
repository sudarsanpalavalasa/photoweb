import os
from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from functools import wraps
from flask import request, jsonify

db = SQLAlchemy()

# ============================================================================
# DATABASE MODELS
# ============================================================================

class User(db.Model):
    """User model for admin authentication"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='admin')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        """Hash and set password"""
        self.password = generate_password_hash(password)
    
    def check_password(self, password):
        """Verify password"""
        return check_password_hash(self.password, password)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Portfolio(db.Model):
    """Portfolio model for photography work"""
    __tablename__ = 'portfolio'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50), nullable=False)
    image_url = db.Column(db.String(500), nullable=False)
    featured = db.Column(db.Boolean, default=False)
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'category': self.category,
            'image_url': self.image_url,
            'featured': self.featured,
            'order': self.order,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Service(db.Model):
    """Service model for photography services"""
    __tablename__ = 'services'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.String(100), nullable=False)
    duration = db.Column(db.String(100))
    features = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'price': self.price,
            'duration': self.duration,
            'features': self.features.split(',') if self.features else [],
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Testimonial(db.Model):
    """Testimonial model for client reviews"""
    __tablename__ = 'testimonials'
    
    id = db.Column(db.Integer, primary_key=True)
    client_name = db.Column(db.String(200), nullable=False)
    testimonial = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, default=5)
    project_type = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'client_name': self.client_name,
            'testimonial': self.testimonial,
            'rating': self.rating,
            'project_type': self.project_type,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Contact(db.Model):
    """Contact model for inquiry messages"""
    __tablename__ = 'contacts'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20))
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'message': self.message,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Content(db.Model):
    """Content model for page sections (hero, about, contact)"""
    __tablename__ = 'content'
    
    id = db.Column(db.Integer, primary_key=True)
    section = db.Column(db.String(50), unique=True, nullable=False)
    title = db.Column(db.String(200))
    subtitle = db.Column(db.String(500))
    content = db.Column(db.Text)
    image_url = db.Column(db.String(500))
    button_text = db.Column(db.String(100))
    button_link = db.Column(db.String(500))
    social_links = db.Column(db.Text)  # JSON string
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """Convert to dictionary"""
        import json
        return {
            'id': self.id,
            'section': self.section,
            'title': self.title,
            'subtitle': self.subtitle,
            'content': self.content,
            'image_url': self.image_url,
            'button_text': self.button_text,
            'button_link': self.button_link,
            'social_links': json.loads(self.social_links) if self.social_links else {},
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


# ============================================================================
# AUTHENTICATION UTILITIES
# ============================================================================

def create_token(user_id, secret_key, expiration_days=7):
    """Create JWT token"""
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(days=expiration_days)
    }
    return jwt.encode(payload, secret_key, algorithm='HS256')


def decode_token(token, secret_key):
    """Decode JWT token"""
    try:
        payload = jwt.decode(token, secret_key, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def token_required(f):
    """Decorator to protect routes with JWT authentication"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(' ')[1]  # Bearer <token>
            except IndexError:
                return jsonify({'message': 'Token is invalid'}), 401
        
        if not token:
            return jsonify({'message': 'No authentication token, access denied'}), 401
        
        from flask import current_app
        payload = decode_token(token, current_app.config['JWT_SECRET_KEY'])
        
        if not payload:
            return jsonify({'message': 'Token is not valid or has expired'}), 401
        
        user = User.query.get(payload['user_id'])
        
        if not user:
            return jsonify({'message': 'User not found'}), 401
        
        if user.role != 'admin':
            return jsonify({'message': 'Access denied. Admin only.'}), 403
        
        request.current_user = user
        return f(*args, **kwargs)
    
    return decorated


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def allowed_file(filename):
    """Check if file extension is allowed"""
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
