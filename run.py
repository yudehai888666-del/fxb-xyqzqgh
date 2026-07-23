import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=int(os.environ.get("ACADEMIC_PLANNING_PORT", "5050")),
        debug=True,
    )
