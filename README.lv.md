# 🏄‍♂️ SurfSense (Pielāgota Versija)

Personīgā AI Meklētājprogramma & Zināšanu Asistents

Atvērtā Koda Alternatīva Perplexity AI / NotebookLM

[![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)
[![Next.js 15](https://img.shields.io/badge/Next.js-15-black.svg)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-Python-brightgreen.svg)](https://fastapi.tiangolo.com)
[![PostgreSQL 17](https://img.shields.io/badge/PostgreSQL-17-blue.svg)](https://postgresql.org)

🌍 **Valodas**: [English](README.md) | [Latviešu](README.lv.md) | [Svenska](README.sv.md)

## Par Šo Versiju

Šī ir pielāgota un uzlabota [MODSetter/SurfSense](https://github.com/MODSetter/SurfSense) versija personīgai zināšanu pārvaldībai.

### Galvenās Atšķirības no Oriģināla

✅ **Uzlabota Drošība**: CSRF aizsardzība, drošības header'i, SSRF prevencija  
✅ **VPS Izvietošana**: Gatavs risinājums ar Nginx + systemd  
✅ **Daudzvalodu Atbalsts**: Angļu, latviešu, zviedru valodas saskarne  
✅ **Pielāgotas Integrācijas**: Īpaši savienotāji un darbplūsmas  
✅ **Lokālie AI Modeļi**: Ollama integrācija ar Mistral-Nemo & TildeOpen

## Iespējas

### 🤖 AI Meklēšana
- **Tīmekļa meklēšana**: Google Search API integrācija
- **Dokumentu meklēšana**: Lokālie faili, PDF, e-pasti, Notion, Google Drive
- **Koda meklēšana**: GitHub repozitoriju integrācija
- **Pielāgoti savienotāji**: RSS kanāli, Jellyfin, Airtable, Linear, Slack

### 🔒 Privātums & Drošība
- **Pašmitināts**: Pilna datu īpašumtiesības uz personīgās infrastruktūras
- **Drošības nostiprinājumi**: HSTS, CSP header'i, ātruma ierobežošana, CSRF tokeni
- **Lokālie AI modeļi**: Modeļi darbojas tikai uz jūsu infrastruktūras
- **Bez ārējās izsekošanas**: Nulles trešo pušu analītika

## Tehnoloģijas

- **Priekšgals**: Next.js 15, React 19, TailwindCSS, TypeScript
- **Aizmugure**: FastAPI, Python 3.12, Celery, Redis
- **Datubāze**: PostgreSQL 17 ar pgvector semantiskai meklēšanai
- **AI dzinējs**: Ollama (Mistral-Nemo, TildeOpen), LlamaIndex
- **Infrastruktūra**: Debian VPS, Nginx, systemd pakalpojumi

## Instalēšana

Skat. [oriģinālā SurfSense dokumentācija](https://github.com/MODSetter/SurfSense) pamata uzstādīšanai.

Pielāgotie norādījumi šai versijai: [CLAUDE.md](CLAUDE.md) (VPS-specifiskas protokolos).

## Dokumentācija

- **[CLAUDE.md](CLAUDE.md)** - AI asistentas instrukcijas & VPS izvietošanas protokols
- **[Oriģinālā SurfSense dokumentācija](https://github.com/MODSetter/SurfSense)** - Augstāka līmeņa dokumentācija

## Atsauces

- **Sākotnējais projekts**: [MODSetter/SurfSense](https://github.com/MODSetter/SurfSense)
- **Uzturētājs**: Ojārs Kapteinis
- **Licence**: MIT (tāda pati kā augstāk)

## Licence

MIT Licence - Skat. [LICENSE](LICENSE) datnei detaļas.

---

**Pēdējo reizi atjaunots**: 2025. gada 31. decembris
