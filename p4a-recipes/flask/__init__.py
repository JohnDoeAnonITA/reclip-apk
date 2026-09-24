"""Local override of python-for-android's `flask` recipe.

p4a v2024.01.21 pins Flask 2.0.3 (2021), which cannot import `url_quote` from
the modern Werkzeug (3.x) that pip installs -> ImportError at runtime.
This recipe uses a modern Flask compatible with Werkzeug 3.x.

Referenced from buildozer.spec via:  p4a.local_recipes = ./p4a-recipes
"""

from pythonforandroid.recipe import PythonRecipe


class FlaskRecipe(PythonRecipe):
    version = "3.1.0"
    url = "https://github.com/pallets/flask/archive/{version}.zip"

    depends = ["setuptools"]
    python_depends = [
        "jinja2",
        "werkzeug",
        "markupsafe",
        "itsdangerous",
        "click",
        "blinker",
    ]

    call_hostpython_via_targetpython = False
    install_in_hostpython = False


recipe = FlaskRecipe()
