from setuptools import setup, find_packages

setup(
    name="experiment_tracking",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "sqlalchemy",
        "pandas",
        "pytest",
        "streamlit",
    ],
) 