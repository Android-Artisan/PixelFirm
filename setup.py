from setuptools import setup, find_packages

# Read long description from README.md
with open("README.md", "r", encoding="utf-8") as f:
    long_desc = f.read()

setup(
    name="pixelfirm",
    version="1.0.0",
    description="Download latest Google Pixel factory images by codename",
    long_description=long_desc,
    long_description_content_type="text/markdown",
    author="Android Artisan",
    author_email="romartisan2025@gmail.com",
    url="https://github.com/Android-Artisan/PixelFirm",
    license="GPL-3.0-or-later",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "requests",
        "beautifulsoup4",
        "tqdm",
    ],
    entry_points={
        "console_scripts": [
            "pixelfirm = pixelfirm.cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
    ],
    python_requires=">=3.7",
)

