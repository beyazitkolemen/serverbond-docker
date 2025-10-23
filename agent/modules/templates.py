"""
Template rendering module
"""
import secrets
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

def render(template_dir, template_name, context):
    """Render Jinja2 template"""
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    template = env.get_template(template_name)
    return template.render(context)

def generate_laravel_env(app_name, domain, db_name, db_user, db_pass, shared_mysql_container, shared_redis_container):
    """Generate Laravel .env file content"""
    app_key = "base64:" + secrets.token_urlsafe(32)
    
    return f"""APP_NAME={app_name}
APP_ENV=production
APP_KEY={app_key}
APP_DEBUG=false
APP_URL=https://{domain}

LOG_CHANNEL=stack
LOG_DEPRECATIONS_CHANNEL=null
LOG_LEVEL=debug

DB_CONNECTION=mysql
DB_HOST={shared_mysql_container}
DB_PORT=3306
DB_DATABASE={db_name}
DB_USERNAME={db_user}
DB_PASSWORD={db_pass}

BROADCAST_DRIVER=log
CACHE_DRIVER=redis
FILESYSTEM_DISK=local
QUEUE_CONNECTION=redis
SESSION_DRIVER=redis
SESSION_LIFETIME=120

REDIS_HOST={shared_redis_container}
REDIS_PASSWORD=null
REDIS_PORT=6379

MAIL_MAILER=smtp
MAIL_HOST=mailpit
MAIL_PORT=1025
MAIL_USERNAME=null
MAIL_PASSWORD=null
MAIL_ENCRYPTION=null
MAIL_FROM_ADDRESS="hello@example.com"
MAIL_FROM_NAME="${app_name}"

AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_DEFAULT_REGION=us-east-1
AWS_BUCKET=
AWS_USE_PATH_STYLE_ENDPOINT=false

PUSHER_APP_ID=
PUSHER_APP_KEY=
PUSHER_APP_SECRET=
PUSHER_HOST=
PUSHER_PORT=443
PUSHER_SCHEME=https
PUSHER_APP_CLUSTER=mt1

VITE_APP_NAME="${app_name}"
VITE_PUSHER_APP_KEY=""
VITE_PUSHER_HOST=""
VITE_PUSHER_PORT="443"
VITE_PUSHER_SCHEME="https"
VITE_PUSHER_APP_CLUSTER="mt1"

QUEUE_CONNECTION=redis
"""
