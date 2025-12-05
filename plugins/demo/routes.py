# plugins/demo/routes.py
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from core.config_loader import get_plugin_config, get_plugin_info
from core.database import db
from plugins.demo.models import DemoUser, DemoPost
from sqlalchemy.exc import IntegrityError

#bp = Blueprint("demo", __name__, template_folder="templates", static_folder="static", url_prefix="/demo")
bp = Blueprint("demo", __name__, template_folder="templates", static_folder="static")

# Context processor for plugin configs
@bp.context_processor
def inject_plugin_configs():
    """Inject plugin configurations into templates"""
    return dict(
        plugin_configs=get_plugin_config,
        plugin_infos=get_plugin_info
    )

@bp.route("/")
def index():
    """Main demo page"""
    try:
        users = DemoUser.query.filter_by(is_active=True).all()
        posts = DemoPost.query.filter_by(published=True).order_by(DemoPost.created_at.desc()).limit(10).all()
        
        return render_template("index.html", users=users, posts=posts)
    except Exception as e:
        print(f"Error in demo index: {e}")
        return render_template("index.html", users=[], posts=[], error=str(e))

@bp.route("/users")
def users():
    """List all users"""
    try:
        all_users = DemoUser.query.all()
        return render_template("users.html", users=all_users)
    except Exception as e:
        return render_template("users.html", users=[], error=str(e))

@bp.route("/user/create", methods=["GET", "POST"])
def create_user():
    """Create a new user"""
    if request.method == "POST":
        try:
            username = request.form.get("username")
            email = request.form.get("email")
            github_id = request.form.get("github_id")
            
            if not username or not email:
                flash("Username and email are required", "error")
                return redirect(url_for("demo.create_user"))
            
            new_user = DemoUser(
                username=username,
                email=email,
                github_id=github_id if github_id else None
            )
            
            db.session.add(new_user)
            db.session.commit()
            
            flash(f"User {username} created successfully!", "success")
            return redirect(url_for("demo.users"))
            
        except IntegrityError:
            db.session.rollback()
            flash("Username or email already exists", "error")
            return redirect(url_for("demo.create_user"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error creating user: {str(e)}", "error")
            return redirect(url_for("demo.create_user"))
    
    return render_template("create_user.html")

@bp.route("/posts")
def posts():
    """List all posts"""
    try:
        all_posts = DemoPost.query.order_by(DemoPost.created_at.desc()).all()
        return render_template("posts.html", posts=all_posts)
    except Exception as e:
        return render_template("posts.html", posts=[], error=str(e))

@bp.route("/post/create", methods=["GET", "POST"])
def create_post():
    """Create a new post"""
    if request.method == "POST":
        try:
            title = request.form.get("title")
            content = request.form.get("content")
            author_id = request.form.get("author_id")
            published = request.form.get("published") == "on"
            
            if not title or not content or not author_id:
                flash("Title, content, and author are required", "error")
                return redirect(url_for("demo.create_post"))
            
            new_post = DemoPost(
                title=title,
                content=content,
                author_id=int(author_id),
                published=published
            )
            
            db.session.add(new_post)
            db.session.commit()
            
            flash(f"Post '{title}' created successfully!", "success")
            return redirect(url_for("demo.posts"))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Error creating post: {str(e)}", "error")
            return redirect(url_for("demo.create_post"))
    
    try:
        users = DemoUser.query.filter_by(is_active=True).all()
        return render_template("create_post.html", users=users)
    except Exception as e:
        return render_template("create_post.html", users=[], error=str(e))

# API endpoints
@bp.route("/api/users", methods=["GET"])
def api_users():
    """Get all users as JSON"""
    try:
        users = DemoUser.query.all()
        return jsonify([user.to_dict() for user in users])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route("/api/posts", methods=["GET"])
def api_posts():
    """Get all posts as JSON"""
    try:
        posts = DemoPost.query.all()
        return jsonify([post.to_dict() for post in posts])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route("/api/user/<int:user_id>", methods=["GET"])
def api_user(user_id):
    """Get a specific user as JSON"""
    try:
        user = DemoUser.query.get_or_404(user_id)
        return jsonify(user.to_dict())
    except Exception as e:
        return jsonify({"error": str(e)}), 404

def register(app):
    """Register blueprint with Flask app"""
    app.register_blueprint(bp)
    print(f"    🔗 Demo plugin routes registered at /demo")