"""Start the Sarawak Tourism Information System development server."""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
