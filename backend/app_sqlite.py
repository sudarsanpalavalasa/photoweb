import os
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from email_validator import validate_email, EmailNotValidError
from models_sqlite import db, User, Portfolio, Service, Testimonial, Contact, Content, create_token, token_required, allowed_file

# Set template and static folders to frontend directory
app = Flask(__name__, 
            template_folder='../frontend',
            static_folder='../frontend',
            static_url_path='')

# Configuration
app.config['SECRET_KEY'] = 'your_super_secret_key_change_this_in_production'
app.config['JWT_SECRET_KEY'] = 'your_jwt_secret_key_change_this'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///photographer_portfolio.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB max file size

# Initialize database
db.init_app(app)

# Enable CORS
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Create uploads folder if it doesn't exist
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Create database tables
with app.app_context():
    db.create_all()
    print("✅ Database tables created successfully!")

# ============================================================================
# STATIC FILE ROUTES
# ============================================================================

@app.route('/')
def index():
    """Serve the main index.html page"""
    return send_from_directory('../frontend', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    """Serve static files (HTML, CSS, JS, images)"""
    if os.path.exists(os.path.join('../frontend', path)):
        return send_from_directory('../frontend', path)
    elif path.endswith('.html'):
        return send_from_directory('../frontend', 'index.html')
    return jsonify({'message': 'Resource not found'}), 404

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded files"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'OK', 'message': 'Server is running', 'database': 'SQLite'}), 200

# ============================================================================
# AUTHENTICATION ROUTES
# ============================================================================

@app.route('/api/auth/register', methods=['POST'])
def register():
    """Register new admin user"""
    try:
        data = request.get_json()
        
        # Validation
        if not data.get('username') or not data.get('email') or not data.get('password'):
            return jsonify({'message': 'All fields are required'}), 400
        
        # Validate email
        try:
            validate_email(data['email'])
        except EmailNotValidError:
            return jsonify({'message': 'Invalid email address'}), 400
        
        # Check if user already exists
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'message': 'Username already exists'}), 400
        
        if User.query.filter_by(email=data['email'].lower()).first():
            return jsonify({'message': 'Email already exists'}), 400
        
        # Create new user
        user = User(
            username=data['username'],
            email=data['email'].lower(),
            role='admin'
        )
        user.set_password(data['password'])
        
        db.session.add(user)
        db.session.commit()
        
        # Create token
        token = create_token(user.id, app.config['JWT_SECRET_KEY'])
        
        return jsonify({
            'token': token,
            'user': user.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Server error: {str(e)}'}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login admin user"""
    try:
        data = request.get_json()
        
        if not data.get('username') or not data.get('password'):
            return jsonify({'message': 'Username and password are required'}), 400
        
        # Find user
        user = User.query.filter_by(username=data['username']).first()
        
        if not user or not user.check_password(data['password']):
            return jsonify({'message': 'Invalid credentials'}), 401
        
        # Create token
        token = create_token(user.id, app.config['JWT_SECRET_KEY'])
        
        return jsonify({
            'token': token,
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'Server error: {str(e)}'}), 500

@app.route('/api/auth/verify', methods=['GET'])
def verify_token():
    """Verify JWT token"""
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not token:
            return jsonify({'message': 'No token provided'}), 401
        
        from models_sqlite import decode_token
        payload = decode_token(token, app.config['JWT_SECRET_KEY'])
        
        if not payload:
            return jsonify({'message': 'Invalid or expired token'}), 401
        
        user = User.query.get(payload['user_id'])
        
        if not user:
            return jsonify({'message': 'User not found'}), 401
        
        return jsonify({'user': user.to_dict()}), 200
        
    except Exception as e:
        return jsonify({'message': f'Server error: {str(e)}'}), 500

# ============================================================================
# PORTFOLIO ROUTES
# ============================================================================

@app.route('/api/portfolio', methods=['GET'])
def get_portfolio():
    """Get all portfolio items"""
    try:
        items = Portfolio.query.order_by(Portfolio.order.desc(), Portfolio.created_at.desc()).all()
        return jsonify([item.to_dict() for item in items]), 200
    except Exception as e:
        return jsonify({'message': f'Server error: {str(e)}'}), 500

@app.route('/api/portfolio/<int:id>', methods=['GET'])
def get_portfolio_item(id):
    """Get single portfolio item"""
    try:
        item = Portfolio.query.get_or_404(id)
        return jsonify(item.to_dict()), 200
    except Exception as e:
        return jsonify({'message': f'Server error: {str(e)}'}), 500

@app.route('/api/portfolio', methods=['POST'])
@token_required
def create_portfolio():
    """Create portfolio item (admin only)"""
    try:
        if 'image' not in request.files:
            return jsonify({'message': 'Image is required'}), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({'message': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'message': 'Invalid file type'}), 400
        
        # Save file
        filename = secure_filename(file.filename)
        filename = f"{datetime.utcnow().timestamp()}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Create portfolio entry
        portfolio = Portfolio(
            title=request.form.get('title'),
            description=request.form.get('description', ''),
            category=request.form.get('category'),
            image_url=f'/uploads/{filename}',
            featured=request.form.get('featured') == 'true',
            order=int(request.form.get('order', 0))
        )
        
        db.session.add(portfolio)
        db.session.commit()
        
        return jsonify(portfolio.to_dict()), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Server error: {str(e)}'}), 500

@app.route('/api/portfolio/<int:id>', methods=['PUT'])
@token_required
def update_portfolio(id):
    """Update portfolio item (admin only)"""
    try:
        item = Portfolio.query.get_or_404(id)
        
        # Handle new image upload
        if 'image' in request.files and request.files['image'].filename != '':
            file = request.files['image']
            if allowed_file(file.filename):
                # Delete old image
                if item.image_url:
                    old_image = os.path.basename(item.image_url)
                    old_path = os.path.join(app.config['UPLOAD_FOLDER'], old_image)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                
                # Save new image
                filename = secure_filename(file.filename)
                filename = f"{datetime.utcnow().timestamp()}_{filename}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                item.image_url = f'/uploads/{filename}'
        
        # Update fields from form data
        if request.form.get('title'):
            item.title = request.form.get('title')
        if request.form.get('description') is not None:
            item.description = request.form.get('description')
        if request.form.get('category'):
            item.category = request.form.get('category')
        if request.form.get('featured') is not None:
            item.featured = request.form.get('featured') == 'true'
        if request.form.get('order') is not None:
            item.order = int(request.form.get('order'))
        
        db.session.commit()
        return jsonify(item.to_dict()), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Server error: {str(e)}'}), 500

@app.route('/api/portfolio/<int:id>', methods=['DELETE'])
@token_required
def delete_portfolio(id):
    """Delete portfolio item (admin only)"""
    try:
        item = Portfolio.query.get_or_404(id)
        
        # Delete image file
        if item.image_url:
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(item.image_url))
            if os.path.exists(image_path):
                os.remove(image_path)
        
        db.session.delete(item)
        db.session.commit()
        
        return jsonify({'message': 'Portfolio item deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Server error: {str(e)}'}), 500

# ============================================================================
# SERVICES ROUTES
# ============================================================================

@app.route('/api/services', methods=['GET'])
def get_services():
    """Get all services"""
    try:
        services = Service.query.order_by(Service.created_at.desc()).all()
        return jsonify([service.to_dict() for service in services]), 200
    except Exception as e:
        return jsonify({'message': f'Server error: {str(e)}'}), 500

@app.route('/api/services', methods=['POST'])
@token_required
def create_service():
    """Create service (admin only)"""
    try:
        data = request.get_json()
        
        service = Service(
            name=data.get('name'),
            description=data.get('description'),
            price=data.get('price'),
            duration=data.get('duration', ''),
            features=','.join(data.get('features', [])) if isinstance(data.get('features'), list) else data.get('features', '')
        )
        
        db.session.add(service)
        db.session.commit()
        
        return jsonify(service.to_dict()), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Server error: {str(e)}'}), 500

@app.route('/api/services/<int:id>', methods=['PUT'])
@token_required
def update_service(id):
    """Update service (admin only)"""
    try:
        service = Service.query.get_or_404(id)
        data = request.get_json()
        
        if data.get('name'):
            service.name = data['name']
        if data.get('description'):
            service.description = data['description']
        if data.get('price'):
            service.price = data['price']
        if data.get('duration') is not None:
            service.duration = data['duration']
        if data.get('features'):
            service.features = ','.join(data['features']) if isinstance(data['features'], list) else data['features']
        
        db.session.commit()
        return jsonify(service.to_dict()), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Server error: {str(e)}'}), 500

@app.route('/api/services/<int:id>', methods=['DELETE'])
@token_required
def delete_service(id):
    """Delete service (admin only)"""
    try:
        service = Service.query.get_or_404(id)
        db.session.delete(service)
        db.session.commit()
        
        return jsonify({'message': 'Service deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Server error: {str(e)}'}), 500

# ============================================================================
# TESTIMONIALS ROUTES
# ============================================================================

@app.route('/api/testimonials', methods=['GET'])
def get_testimonials():
    """Get all testimonials"""
    try:
        testimonials = Testimonial.query.order_by(Testimonial.created_at.desc()).all()
        return jsonify([t.to_dict() for t in testimonials]), 200
    except Exception as e:
        return jsonify({'message': f'Server error: {str(e)}'}), 500

@app.route('/api/testimonials', methods=['POST'])
@token_required
def create_testimonial():
    """Create testimonial (admin only)"""
    try:
        data = request.get_json()
        
        testimonial = Testimonial(
            client_name=data.get('client_name'),
            testimonial=data.get('testimonial'),
            rating=data.get('rating', 5),
            project_type=data.get('project_type', '')
        )
        
        db.session.add(testimonial)
        db.session.commit()
        
        return jsonify(testimonial.to_dict()), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Server error: {str(e)}'}), 500

@app.route('/api/testimonials/<int:id>', methods=['PUT'])
@token_required
def update_testimonial(id):
    """Update testimonial (admin only)"""
    try:
        testimonial = Testimonial.query.get_or_404(id)
        data = request.get_json()
        
        if data.get('client_name'):
            testimonial.client_name = data['client_name']
        if data.get('testimonial'):
            testimonial.testimonial = data['testimonial']
        if data.get('rating') is not None:
            testimonial.rating = data['rating']
        if data.get('project_type') is not None:
            testimonial.project_type = data['project_type']
        
        db.session.commit()
        return jsonify(testimonial.to_dict()), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Server error: {str(e)}'}), 500

@app.route('/api/testimonials/<int:id>', methods=['DELETE'])
@token_required
def delete_testimonial(id):
    """Delete testimonial (admin only)"""
    try:
        testimonial = Testimonial.query.get_or_404(id)
        db.session.delete(testimonial)
        db.session.commit()
        
        return jsonify({'message': 'Testimonial deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Server error: {str(e)}'}), 500

# ============================================================================
# CONTACT ROUTES
# ============================================================================

@app.route('/api/contact', methods=['GET'])
@token_required
def get_contacts():
    """Get all contact messages (admin only)"""
    try:
        contacts = Contact.query.order_by(Contact.created_at.desc()).all()
        return jsonify([c.to_dict() for c in contacts]), 200
    except Exception as e:
        return jsonify({'message': f'Server error: {str(e)}'}), 500

@app.route('/api/contact', methods=['POST'])
def create_contact():
    """Submit contact message (public)"""
    try:
        data = request.get_json()
        
        # Validate email
        try:
            validate_email(data.get('email', ''))
        except EmailNotValidError:
            return jsonify({'message': 'Invalid email address'}), 400
        
        contact = Contact(
            name=data.get('name'),
            email=data.get('email'),
            phone=data.get('phone', ''),
            message=data.get('message')
        )
        
        db.session.add(contact)
        db.session.commit()
        
        return jsonify(contact.to_dict()), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Server error: {str(e)}'}), 500

@app.route('/api/contact/<int:id>', methods=['DELETE'])
@token_required
def delete_contact(id):
    """Delete contact message (admin only)"""
    try:
        contact = Contact.query.get_or_404(id)
        db.session.delete(contact)
        db.session.commit()
        
        return jsonify({'message': 'Contact message deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Server error: {str(e)}'}), 500

# ============================================================================
# CONTENT ROUTES
# ============================================================================

@app.route('/api/content/<section>', methods=['GET'])
def get_content(section):
    """Get content by section (public)"""
    try:
        content = Content.query.filter_by(section=section).first()
        if not content:
            return jsonify({'message': 'Content not found'}), 404
        return jsonify(content.to_dict()), 200
    except Exception as e:
        return jsonify({'message': f'Server error: {str(e)}'}), 500

@app.route('/api/content/<section>', methods=['PUT', 'POST'])
@token_required
def update_content(section):
    """Update or create content section (admin only)"""
    try:
        import json
        
        content = Content.query.filter_by(section=section).first()
        
        # Handle JSON data
        if request.is_json:
            data = request.get_json()
            
            if not content:
                content = Content(section=section)
                db.session.add(content)
            
            if 'title' in data:
                content.title = data['title']
            if 'subtitle' in data:
                content.subtitle = data['subtitle']
            if 'content' in data:
                content.content = data['content']
            if 'image_url' in data:
                content.image_url = data['image_url']
            if 'button_text' in data:
                content.button_text = data['button_text']
            if 'button_link' in data:
                content.button_link = data['button_link']
            if 'social_links' in data:
                content.social_links = json.dumps(data['social_links'])
        
        # Handle form data with file upload
        else:
            if not content:
                content = Content(section=section)
                db.session.add(content)
            
            # Handle optional file upload
            if 'image' in request.files and request.files['image'].filename != '':
                file = request.files['image']
                if allowed_file(file.filename):
                    # Delete old image if exists
                    if content.image_url:
                        old_file = content.image_url.replace('/uploads/', '')
                        old_path = os.path.join(app.config['UPLOAD_FOLDER'], old_file)
                        if os.path.exists(old_path):
                            os.remove(old_path)
                    
                    filename = secure_filename(file.filename)
                    filename = f"{datetime.utcnow().timestamp()}_{filename}"
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    content.image_url = f'/uploads/{filename}'
            
            # Get form data
            if request.form.get('title'):
                content.title = request.form.get('title')
            if request.form.get('subtitle'):
                content.subtitle = request.form.get('subtitle')
            if request.form.get('content'):
                content.content = request.form.get('content')
            if request.form.get('button_text'):
                content.button_text = request.form.get('button_text')
            if request.form.get('button_link'):
                content.button_link = request.form.get('button_link')
            if request.form.get('social_links'):
                content.social_links = request.form.get('social_links')
        
        db.session.commit()
        return jsonify(content.to_dict()), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Server error: {str(e)}'}), 500

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'message': 'Resource not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'message': 'Internal server error'}), 500

# ============================================================================
# RUN APPLICATION
# ============================================================================

if __name__ == '__main__':
    print("🚀 Starting Flask server with SQLite database...")
    print("📊 Database: photographer_portfolio.db")
    print("🌐 Server: http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)
