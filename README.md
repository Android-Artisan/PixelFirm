# PixelFirm

> A CLI tool to download the latest Google Pixel factory image by codename

---

## Table of Contents

- [About](#about)  
- [Features](#features)  
- [Requirements](#requirements)  
- [Installation](#installation)  
- [Usage](#usage)  
- [Manifest Details](#manifest-details)  
- [Updating / Offline Mode](#updating--offline-mode)  
- [Contributing](#contributing)  
- [License](#license)  
- [Contact](#contact)  

---

## About

PixelFirm is a command‑line utility written in Python that lets you easily fetch the latest Google Pixel firmware (factory images) using the device’s codename. It retrieves a manifest (online or fallback) and uses that to download the needed image.

---

## Features

- Downloads the latest Pixel factory image for any Pixel device, given its codename.  
- Automatically fetches manifest data from GitHub / Google Developers.  
- Offline support via local manifest fallback.  
- Daily updating via GitHub Actions (keeps manifest current).  

---

## Requirements

- Python 3.x (preferably 3.7+)  
- Standard Python libraries; see `requirements.txt`  
- Internet connection (for manifest and firmware download)  

---

## Installation

You can install PixelFirm in several ways:

```bash
# Option 1: Clone and install locally
git clone https://github.com/Android-Artisan/PixelFirm.git
cd PixelFirm
pip install -r requirements.txt
python setup.py install

# Option 2: Install via pip (if comming soon)
# pip install pixelfirm
```

---

## Usage

```bash
pixelfirm -c <codename>
```

- Replace `<codename>` with the device’s codename (e.g. `sailfish`, `walleye`, etc.).  
- The tool will download the latest factory image for that codename.

Example:

```bash
pixelfirm -c coral
```

---

## Manifest Details

- The tool looks for `manifest.json` hosted on GitHub which is generated via scraping of Google’s Android factory images page.  
- If online manifest fetch fails, it falls back to a local copy included in the project.  

---

## Updating / Offline Mode

- The manifest is automatically updated daily via a GitHub Actions workflow.  
- If you are offline or GitHub is inaccessible, PixelFirm will use the local manifest to find the latest known image.

---

## Contributing

Contributions are welcome! Here are some ways you can help:

- Add support for new Pixel codenames  
- Improve the manifest scraper (handle edge cases)  
- Fix bugs and improve stability  
- Improve documentation and usage examples  

If you’d like to contribute, please:

1. Fork the repo  
2. Make your changes in a feature branch  
3. Test thoroughly  
4. Submit a pull request  

---

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).

---

## Contact

For questions, suggestions, or bug reports, open an issue or reach out via GitHub.
