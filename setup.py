from setuptools import find_packages, setup


setup(
    name="ai-daily-digest",
    version="0.1.0",
    package_dir={"": "src"},
    packages=find_packages("src"),
    install_requires=[
        "feedparser>=6.0.11",
        "httpx>=0.27.0",
        "PyYAML>=6.0.1",
        "python-dotenv>=1.0.1",
    ],
    extras_require={"dev": ["pytest>=8.0.0", "pytest-httpx>=0.30.0"]},
    entry_points={"console_scripts": ["ai-daily-digest=ai_daily_digest.cli:main"]},
)
