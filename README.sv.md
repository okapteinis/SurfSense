# 🏄‍♂️ SurfSense (Anpassad Version)

Personlig AI-Sökmotor & Kunskapsassistent

Öppen Källkod Alternativ till Perplexity AI / NotebookLM

[![Licens: MIT](https://img.shields.io/badge/Licens-MIT-yellow.svg)](LICENSE)
[![Next.js 15](https://img.shields.io/badge/Next.js-15-black.svg)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-Python-brightgreen.svg)](https://fastapi.tiangolo.com)
[![PostgreSQL 17](https://img.shields.io/badge/PostgreSQL-17-blue.svg)](https://postgresql.org)

🌍 **Språk**: [English](README.md) | [Latviešu](README.lv.md) | [Svenska](README.sv.md)

## Om Denna Version

Detta är en anpassad och förbättrad fork av [MODSetter/SurfSense](https://github.com/MODSetter/SurfSense) för personlig kunskapshantering.

### Viktiga Skillnader från Upstream

✅ **Förbättrad Säkerhet**: CSRF-skydd, säkerhetsheaders, SSRF-prevention  
✅ **VPS-Distribution**: Produktionsklar Nginx + systemd-konfiguration  
✅ **Flerspråkigt Gränssnitt**: Engelska, lettiska, svenska  
✅ **Anpassade Integrationer**: Skräddarsydda kopplingar och arbetsflöden  
✅ **Lokala AI-Modeller**: Ollama med Mistral-Nemo & TildeOpen

## Funktioner

### 🤖 AI-Driven Sökning
- **Webbssökning**: Google Search API-integration
- **Dokumentssökning**: Lokala filer, PDF:er, e-postmeddelanden, Notion, Google Drive
- **Kodssökning**: GitHub-databasintegration
- **Anpassade kopplingar**: RSS-kanaler, Jellyfin, Airtable, Linear, Slack

### 🔒 Integetet & Säkerhet
- **Självhostad**: Fullständig datakontroll på din egen infrastruktur
- **Säkerhetshårdad**: HSTS, CSP-headers, hastighetsbegränsning, CSRF-tokens
- **Lokala AI-modeller**: Modellerna körs helt på din infrastruktur
- **Ingen extern spårning**: Noll tredjeparts-analitik

## Teknologier

- **Frontend**: Next.js 15, React 19, TailwindCSS, TypeScript
- **Backend**: FastAPI, Python 3.12, Celery, Redis
- **Databas**: PostgreSQL 17 med pgvector för semantisk sökning
- **AI-Motor**: Ollama (Mistral-Nemo, TildeOpen), LlamaIndex
- **Infrastruktur**: Debian VPS, Nginx, systemd-tjänster

## Installation

Se [original SurfSense-dokumentation](https://github.com/MODSetter/SurfSense) för grundläggande konfiguration.

Anpassade instruktioner för denna fork: [CLAUDE.md](CLAUDE.md) (VPS-specifika protokoll).

## Dokumentation

- **[CLAUDE.md](CLAUDE.md)** - AI-assistentinstruktioner & VPS-distributionsprotokoll
- **[Original SurfSense Docs](https://github.com/MODSetter/SurfSense)** - Uppströmsdokumentation

## Erkännanden

- **Uppströmsprojekt**: [MODSetter/SurfSense](https://github.com/MODSetter/SurfSense)
- **Underhållare**: Ojārs Kapteinis
- **Licens**: MIT (samma som uppströms)

## Licens

MIT-licens - Se [LICENSE](LICENSE) för detaljer.

---

**Senast uppdaterad**: 31 december 2025
