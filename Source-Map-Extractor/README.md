# Source Map Extractor – Automated React/JS Source Code Downloader

This tool automatically downloads JavaScript bundles from a webpage, detects their source maps, and reconstructs the original source files from those maps.  
It works for React, Vue, Angular, or any JavaScript build system that ships source maps.

Ideal for:
- Auditing your own frontend builds  
- Recovering accidentally exposed source maps  
- Debugging bundled/minified JavaScript  
- Reconstructing source code from `.map` files  

> ⚠️ **Use responsibly.**  
> Only run this tool on websites you own or have explicit permission to analyze. Downloading/copying third-party sources without permission may violate legal terms.

---

## ✨ Features
- Automatically scans any webpage for:
  - `<script src="...">` tags  
  - Inline scripts with mapping references  
- Extracts `sourceMappingURL` from bundled JS  
- Downloads `.map` files or decodes inline Base64 maps  
- Reconstructs the full original file tree using `sources` + `sourcesContent`  
- Attempts fallback fetching for missing source content  
- Saves all recovered files into an organized folder structure  

---

## 📦 Requirements

Install dependencies:

```bash
pip install requests beautifulsoup4

🚀 Usage
Basic command
python grab_sources_from_site.py https://example.com ./output_dir
