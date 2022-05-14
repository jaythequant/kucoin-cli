import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="kucoin-cli",
    version="0.0.1",
    author="James VanLandingham",
    author_email="jameslvanlandingham@gmail.com",
    description="Kucoin API and websocket client",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/jaythequant/kucoin-cli",
    project_urls={
        "Kucoin Client": "https://github.com/jaythequant/kucoin-cli",
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
    ],
    python_requires=">=3.9",
)
