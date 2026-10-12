# ⚡ ChatGPT SuperActions Hub (All-in-One Repository)

> Единый супер-репозиторий для расширения возможностей ChatGPT: отборный каталог ТОП-50 инструментов и готовый production-бэкенд для подключения Custom Actions в 1 клик.

---

## 🌟 Архитектура репозитория (2 Части)

Репозиторий разделён на 2 логические части:

```
analyzer/
├── 📁 catalog/                  # [Часть 1] Каталог ТОП-50 инструментов
│   ├── top_50_repositories.md  # Подробный каталог с описанием и кейсами
│   ├── catalog.json            # Машиночитаемый JSON для интеграций и API
│   └── generate_json.py        # Скрипт автоматической генерации базы
│
├── 📁 server/                   # [Часть 2] Готовый FastAPI бэкенд для ChatGPT
│   ├── main.py                 # Главный сервер приложения
│   ├── openapi.yaml            # Готовая спецификация OpenAPI 3.0 (YAML)
│   ├── openapi.json            # Спецификация OpenAPI 3.0 (JSON)
│   ├── requirements.txt        # Список зависимостей
│   ├── export_openapi.py       # Экспортер OpenAPI-схем
│   └── 📁 routers/             # Модули готовых инструментов
│       ├── catalog.py          # Доступ к каталогу топ-50 репозиториев
│       ├── web.py              # Парсинг и очистка веб-страниц по URL
│       ├── youtube.py          # Извлечение субтитров и транскриптов YouTube
│       ├── crypto.py           # Живые котировки крипторынка (CoinGecko/Binance)
│       └── finance.py          # Конвертер фиатных мировых валют
│
├── 📁 docs/                     # Инструкции и документация
│   └── chatgpt_setup_guide.md  # Пошаговый гайд по подключению к ChatGPT
│
└── 📁 tests/                    # Набор автотестов (Verification Gate)
    └── test_server.py          # Тестирование всех эндпоинтов (100% Pass)
```

---

## 📚 Часть 1: Каталог ТОП-50 инструментов

В папке `catalog/` собрана проверенная база из 50 репозиториев по 7 направлениям:
1. **Custom Actions & OpenAPI:** Шаблоны экшенов, спецификации и конструкторы.
2. **Web Scraping & Search:** Firecrawl, Jina Reader, DuckDuckGo Search, Crawl4AI.
3. **Мультимедиа & Документы:** YouTube Transcript API, Marker, PyMuPDF, Whisper.
4. **Бизнес-интеграции:** Notion, Telegram (Aiogram), SQLAlchemy, Vanna SQL, Google API.
5. **AI-агенты и MCP:** Model Context Protocol (MCP), CrewAI, LangChain, AutoGen.
6. **Финансы и Web3:** CCXT, CoinGecko, YFinance, Web3.py.
7. **Безопасность:** Pydantic, Guardrails AI, Promptfoo, Langfuse.

Полный список доступен в [catalog/top_50_repositories.md](catalog/top_50_repositories.md).

---

## 🚀 Часть 2: Запуск готового сервера для ChatGPT

### 1. Установка зависимостей
```bash
pip install -r server/requirements.txt
```

### 2. Запуск сервера
```bash
uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
```

* Swagger UI документация: `http://localhost:8000/docs`
* Тестирование работоспособности: `http://localhost:8000/health`

### 3. Подключение к Custom GPT
1. Скопируйте схему из `server/openapi.yaml`.
2. В интерфейсе ChatGPT Custom GPT нажмите **Create new action** и вставьте схему.
3. Подробная инструкция: [docs/chatgpt_setup_guide.md](docs/chatgpt_setup_guide.md).

---

## 🧪 Тестирование и верификация

Все эндпоинты покрыты тестами:
```bash
pytest tests/ -v
```
Статус проверки: **6 passed (100% Green)**.
