# plugins/auth/routes.py
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
import requests
from core.config_loader import get_plugin_config, get_plugin_info
from core.database import db
from core.plugin_manager import get_merged_model
from sqlalchemy.exc import IntegrityError

bp = Blueprint("auth", __name__, template_folder="templates", static_folder="static")

@bp.context_processor
def inject_plugin_configs():
    return dict(
        plugin_configs=get_plugin_config,
        plugin_infos=get_plugin_info
    )


@bp.route('/login')
def login():
    return render_template('auth.html')


@bp.route('/auth/github')
def github_auth():
    """Redirect to GitHub OAuth authorization page"""
    config = get_plugin_config('auth')
    
    # Debug: Print config to see what we got
    print(f"🔍 Auth config loaded: {config}")
    
    # Get values from config
    client_id = config.get('GITHUB_CLIENT_ID')
    redirect_uri = config.get('GITHUB_REDIRECT_URI')
    auth_url = config.get('GITHUB_AUTHORIZE_URL', 'https://github.com/login/oauth/authorize')
    
    # Check if required values are missing or still have placeholder values
    if not client_id or not redirect_uri or client_id.startswith('${') or redirect_uri.startswith('${'):
        return f"""
        <h1>GitHub OAuth Configuration Error</h1>
        <p><strong>Current Configuration Status:</strong></p>
        <ul>
            <li>GITHUB_CLIENT_ID: {'✅ Set' if client_id and not client_id.startswith('${') else '❌ Not set or not loaded from .env'}</li>
            <li>GITHUB_CLIENT_SECRET: {'✅ Set' if config.get('GITHUB_CLIENT_SECRET') and not config.get('GITHUB_CLIENT_SECRET').startswith('${') else '❌ Not set or not loaded from .env'}</li>
            <li>GITHUB_REDIRECT_URI: {'✅ Set' if redirect_uri and not redirect_uri.startswith('${') else '❌ Not set or not loaded from .env'}</li>
        </ul>
        
        <h2>Setup Steps:</h2>
        <ol>
            <li>Make sure you have a <code>.env</code> file in the root directory</li>
            <li>Add these values to your <code>.env</code> file:
                <pre>
GITHUB_CLIENT_ID=your_actual_client_id
GITHUB_CLIENT_SECRET=your_actual_client_secret
GITHUB_REDIRECT_URI=http://127.0.0.1:5000/auth/github/callback
                </pre>
            </li>
            <li>Make sure <code>python-dotenv</code> is installed: <code>pip install python-dotenv</code></li>
            <li>Restart the Flask server</li>
        </ol>
        
        <p><a href="https://github.com/settings/developers" target="_blank">Get GitHub OAuth credentials here</a></p>
        <p><a href="{url_for('auth.login')}">← Back to Login</a></p>
        """, 400
    
    # Build authorization URL
    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'scope': 'user:email',
        'allow_signup': 'true'
    }
    
    query_string = '&'.join([f'{k}={v}' for k, v in params.items()])
    full_auth_url = f"{auth_url}?{query_string}"
    
    print(f"🔗 Redirecting to: {full_auth_url}")
    return redirect(full_auth_url)


@bp.route('/auth/github/callback')
def github_callback():
    """Handle GitHub OAuth callback"""
    code = request.args.get('code')
    error = request.args.get('error')
    
    if error:
        return f'Authorization failed: {error}', 400
    
    if not code:
        return 'Error: No authorization code provided', 400
    
    config = get_plugin_config('auth')
    
    # Exchange code for access token
    token_data = {
        'client_id': config.get('GITHUB_CLIENT_ID'),
        'client_secret': config.get('GITHUB_CLIENT_SECRET'),
        'code': code,
        'redirect_uri': config.get('GITHUB_REDIRECT_URI')
    }
    
    print(f"🔄 Exchanging code for token...")
    
    headers = {'Accept': 'application/json'}
    try:
        response = requests.post(
            config.get('GITHUB_TOKEN_URL', 'https://github.com/login/oauth/access_token'),
            data=token_data,
            headers=headers,
            timeout=10
        )
        
        if response.status_code != 200:
            print(f"❌ Token exchange failed: {response.text}")
            return f'Error getting access token: {response.text}', 400
        
        token_response = response.json()
        access_token = token_response.get('access_token')
        
        if not access_token:
            print(f"❌ No access token in response: {token_response}")
            return f'Error: No access token received. Response: {token_response}', 400
        
        print(f"✅ Access token received")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return f'Error connecting to GitHub: {str(e)}', 500
    
    # Get user info from GitHub
    user_headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json'
    }
    
    try:
        user_response = requests.get(
            config.get('GITHUB_USER_URL', 'https://api.github.com/user'),
            headers=user_headers,
            timeout=10
        )
        
        if user_response.status_code != 200:
            print(f"❌ User info request failed: {user_response.text}")
            return f'Error getting user info: {user_response.text}', 400
        
        user_data = user_response.json()
        print(f"✅ User data received: {user_data.get('login', 'unknown')}")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ User info request failed: {e}")
        return f'Error getting user info: {str(e)}', 500
    
    # Get the merged DemoUser model
    DemoUser = get_merged_model('demo_users')
    
    if DemoUser is None:
        print(f"❌ DemoUser model not found")
        return 'Error: User model not found', 500
    
    # Check if user already exists
    github_id = str(user_data['id'])
    existing_user = DemoUser.query.filter_by(github_id=github_id).first()
    
    if existing_user:
        # User exists, log them in
        session['user'] = {
            'id': existing_user.id,
            'username': existing_user.username,
            'email': existing_user.email,
            'github_id': existing_user.github_id,
            'access_token': access_token
        }
        print(f"✅ Existing user logged in: {existing_user.username}")
        return redirect(url_for('auth.dashboard'))
    
    # Create new user
    try:
        new_user = DemoUser(
            username=user_data.get('login', f"user_{github_id}"),
            email=user_data.get('email', ''),
            github_id=github_id,
            is_active=True
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        session['user'] = {
            'id': new_user.id,
            'username': new_user.username,
            'email': new_user.email,
            'github_id': new_user.github_id,
            'access_token': access_token
        }
        
        print(f"✅ New user created: {new_user.username}")
        return redirect(url_for('auth.dashboard'))
        
    except IntegrityError as e:
        db.session.rollback()
        print(f"❌ Database integrity error: {e}")
        return f'Error: Could not create user account. {str(e)}', 500
    except Exception as e:
        db.session.rollback()
        print(f"❌ Unexpected error: {e}")
        return f'Error: {str(e)}', 500


@bp.route('/dashboard')
def dashboard():
    """User dashboard (requires login)"""
    if 'user' not in session:
        return redirect(url_for('auth.login'))
    
    user_data = session['user']
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dashboard</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                max-width: 800px;
                margin: 50px auto;
                padding: 20px;
                background: #f5f5f5;
            }}
            .dashboard {{
                background: white;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            h1 {{ color: #333; }}
            .user-info {{
                background: #f8f9fa;
                padding: 20px;
                border-radius: 5px;
                margin: 20px 0;
            }}
            .user-info p {{
                margin: 10px 0;
                color: #555;
            }}
            .logout-btn {{
                display: inline-block;
                padding: 10px 20px;
                background: #dc3545;
                color: white;
                text-decoration: none;
                border-radius: 5px;
                margin-top: 20px;
            }}
            .logout-btn:hover {{
                background: #c82333;
            }}
        </style>
    </head>
    <body>
        <div class="dashboard">
            <h1>Welcome to Your Dashboard!</h1>
            <div class="user-info">
                <h2>User Information</h2>
                <p><strong>Username:</strong> {user_data.get('username', 'N/A')}</p>
                <p><strong>Email:</strong> {user_data.get('email', 'N/A')}</p>
                <p><strong>GitHub ID:</strong> {user_data.get('github_id', 'N/A')}</p>
                <p><strong>User ID:</strong> {user_data.get('id', 'N/A')}</p>
            </div>
            <a href="{url_for('auth.logout')}" class="logout-btn">Logout</a>
        </div>
    </body>
    </html>
    """


@bp.route('/logout')
def logout():
    """Logout user"""
    session.clear()
    return redirect(url_for('auth.login'))


def register(app):
    """Register blueprint with Flask app"""
    app.register_blueprint(bp)
    print(f"    🔗 Auth plugin routes registered at /auth")