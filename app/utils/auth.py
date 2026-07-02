from functools import wraps

from flask import flash, redirect, url_for
from flask_login import current_user, login_required


def role_required(*roles):
    def decorator(func):
        @wraps(func)
        @login_required
        def wrapper(*args, **kwargs):
            if current_user.is_authenticated and current_user.role not in roles:
                flash("You do not have access to that page.", "danger")
                return redirect(url_for("index"))
            return func(*args, **kwargs)

        return wrapper

    return decorator
