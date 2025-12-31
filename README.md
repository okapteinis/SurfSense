# 🏄‍♂️ SurfSense (Custom Fork)

Personal AI Search Engine & Knowledge Assistant

Open Source Alternative to Perplexity AI / NotebookLM

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Next.js 15](https://img.shields.io/badge/Next.js-15-black.svg)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-Python-brightgreen.svg)](https://fastapi.tiangolo.com)
[![PostgreSQL 17](https://img.shields.io/badge/PostgreSQL-17-blue.svg)](https://postgresql.org)

🌍 **Languages**: [English](README.md) | [Latviešu](README.lv.md) | [Svenska](README.sv.md)

## About This Fork

This is a customized and enhanced fork of [MODSetter/SurfSense](https://github.com/MODSetter/SurfSense), deployed and maintained for personal knowledge management.

### Key Differences from Upstream

✅ **Enhanced Security**: CSRF protection, secure headers, SSRF prevention  
✅ **VPS Deployment**: Production-ready Nginx + systemd configuration  
✅ **Multi-Language UI**: English, Latvian, Swedish interface support  
✅ **Custom Integrations**: Tailored connectors and workflows  
✅ **Local AI Models**: Ollama integration with Mistral-Nemo & TildeOpen

## Features

### 🤖 AI-Powered Search
- **Web Search**: Google Search API integration
- **Document Search**: Local files, PDFs, emails, Notion, Google Drive
- **Code Search**: GitHub repositories integration
- **Custom Connectors**: RSS feeds, Jellyfin, Airtable, Linear, Slack

### 🔒 Privacy & Security
- **Self-Hosted**: Complete data ownership on personal infrastructure
- **Security Hardened**: HSTS, CSP headers, rate limiting, CSRF tokens
- **Local AI**: Models run entirely on your infrastructure
- **No External Tracking**: Zero third-party analytics

## Technologies

- **Frontend**: Next.js 15, React 19, TailwindCSS, TypeScript
- **Backend**: FastAPI, Python 3.12, Celery, Redis
- **Database**: PostgreSQL 17 with pgvector for semantic search
- **AI Engine**: Ollama (Mistral-Nemo, TildeOpen), LlamaIndex
- **Infrastructure**: Debian VPS, Nginx, systemd services

## Installation

See [original SurfSense documentation](https://github.com/MODSetter/SurfSense) for basic setup.

Custom deployment notes for this fork: See [CLAUDE.md](CLAUDE.md) (VPS-specific protocols).

## Documentation

- **[CLAUDE.md](CLAUDE.md)** - AI assistant instructions & VPS deployment protocol
- **[Original SurfSense Docs](https://github.com/MODSetter/SurfSense)** - Upstream documentation

## Credits

- **Upstream Project**: [MODSetter/SurfSense](https://github.com/MODSetter/SurfSense)
- **Maintainer**: Ojārs Kapteinis
- **License**: MIT (same as upstream)

## License

MIT License - See [LICENSE](LICENSE) file for details.

---

**Last Updated**: December 31, 2025
