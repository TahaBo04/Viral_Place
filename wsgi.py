from app import create_app, initialize_database

app = create_app()
initialize_database(app)
