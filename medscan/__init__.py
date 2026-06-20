import os

from flask import Flask

from .db import close_db, init_db_command


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY="dev",
        DATABASE=os.path.join(app.instance_path, "medscan.sqlite"),
        UPLOAD_FOLDER=os.path.join(app.root_path, "..", "uploads"),
        MAX_CONTENT_LENGTH=10 * 1024 * 1024,
        ALLOWED_EXTENSIONS={"png", "jpg", "jpeg", "dcm"},
    )

    if test_config is not None:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    from .db import init_app

    init_app(app)
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)

    from .auth import bp as auth_bp
    from .main import bp as main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    from .db import init_db

    with app.app_context():
        init_db()

    return app
