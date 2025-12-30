# Library Emerge (Django)

## Requirements
- Python 3.10+
- pip
- virtualenv (optional but recommended)

## Setup

```bash
# create virtual environment
python -m venv venv
source venv/bin/activate   # macOS/Linux
# venv\Scripts\activate    # Windows

# install dependencies
pip install -r requirements.txt

# run migrations
python manage.py migrate

# create admin user (optional)
python manage.py createsuperuser

# start server
python manage.py runserver
