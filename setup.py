import setuptools

import swaglyrics_backend

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="swaglyrics_backend",
    version=swaglyrics_backend.__version__,
    author="Aadi Bajpai",
    description="Server side code to communicate with SwagLyrics, manage unsupported songs and make an issue on the "
                "main repo when the program encounters a song it can't fetch lyrics for.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/SwagLyrics/swaglyrics-backend",
    packages=['swaglyrics_backend'],
    install_requires=['flask', 'Flask-Limiter', 'GitPython', 'flask_sqlalchemy', 'swaglyrics', 'requests'],
    extras_require={
        'dev': [
            'pytest',
            'pytest-cov',
            'codecov'
        ]
    },
)
