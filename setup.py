from setuptools import setup, find_packages

setup(
    name="teachproxy",
    version="0.1.0",
    packages=find_packages(include=["gateway", "gateway.*", "admin", "admin.*"]),
    python_requires=">=3.12",
)