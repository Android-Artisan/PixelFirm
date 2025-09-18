from setuptools import setup, find_packages
setup(
    name="pixelfirm",
    version="1.0.0",
    description="Download latest Google Pixel factory images by codename",
    packages=find_packages(),
    install_requires=["requests","beautifulsoup4","tqdm"],
    entry_points={
        "console_scripts": [
            "pixelfirm = pixelfirm.cli:main",
        ],
    },
)
