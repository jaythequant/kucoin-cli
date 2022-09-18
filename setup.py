import setuptools

with open("README.rst", "r", encoding="utf-8") as fh:
    long_description = fh.read()

version = "1.3.5"

setuptools.setup(
    name="kucoin-cli",
    version=version,
    author="James VanLandingham",
    author_email="jameslvanlandingham@gmail.com",
    description="Kucoin API and WebSocket client",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/jaythequant/kucoin-cli",
    project_urls={
        "Github Dist": "https://github.com/jaythequant/kucoin-cli",
        "PyPi Dist": f"https://pypi.org/project/kucoin-cli/{version}/",
        "Readthedocs": "https://kucoin-cli.readthedocs.io/en/latest/",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    packages=setuptools.find_packages(where="."),
    install_requires=[
        "asyncio",
        "certifi",
        "charset-normalizer",
        "idna",
        "numpy",
        "pandas",
        "python-dateutil",
        "pytz",
        "requests",
        "six",
        "urllib3",
        "websockets",
        "timedelta",
        "sqlalchemy",
        "progress",
    ],
    python_requires=">=3.8",
)
